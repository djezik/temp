import random
from datetime import datetime, timedelta
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram.error as err

import os
import db
from models import *
from queued_bot import Bot
import settings
import payment_server.server_settings as payment_settings
import payment_server.server_utils as payment_utils


def register_new_user(session: db.Session, user_id, invited_by=None) -> User:
    new_chat_state = ChatState(id=user_id, node=0, user_id=user_id)
    new_user = User(
        id=user_id,
        permissions=PermissionsLevels.USER,
        last_activity=datetime.utcnow(),
        chat_state=new_chat_state
    )
    session.add_all([new_chat_state, new_user])

    if invited_by is not None:
        session.commit()
        new_referral_link = ReferralLink(
            user_id=user_id,
            invited_by_id=invited_by
        )
        inviter = session.query(User).filter_by(id=invited_by).one_or_none()

        if inviter is not None:
            inviter.referral_cash += settings.REFERRAL_BONUS * 100
            inviter.cash += settings.REFERRAL_BONUS * 100
            session.add(new_referral_link)

    session.commit()
    return new_user


# TODO: Запретить инвалидные обновления
def prepare_user_data(update: Update, user_data: dict, invited_by=None):
    """
    :return: bool, is user is new or not
    """
    session = db.Session()
    result = False
    if len(user_data) == 0:
        # have to fetch data about user from db

        user_id = None
        chat_id = None
        if update.message:
            user_id = update.message.from_user.id
            chat_id = update.message.chat.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            chat_id = update.callback_query.from_user.id

        if user_id is None or chat_id is None:  # TODO
            session.close()
            raise TypeError("Update have neither message nor callback_query")

        user = session.query(User).get(user_id)
        if user is None:
            # There is no users with such id, have to create new one in db
            user = register_new_user(session, update.message.from_user.id, invited_by)
            result = True
        user_data["id"] = user.id
        chat_state = session.query(ChatState).filter_by(user_id=user_data["id"]).first()
        user_data["node"] = chat_state.node
        user_data["chat_id"] = chat_id

    current_user = session.query(User).get(user_data["id"])
    current_user.last_activity = datetime.utcnow()
    current_user.blocked = False
    session.commit()
    session.close()
    return result


def set_state(user_id, user_data, new_state):
    session = db.Session()
    session.query(ChatState).filter_by(user_id=user_id).first().node = new_state
    user_data["node"] = new_state
    session.commit()
    session.close()


def try_add_channel(bot: Bot, candidate: str, channel_model_class):
    if candidate[0] != "@":
        candidate = "@" + candidate

    try:
        channel = bot.get_chat(chat_id=candidate)
    except err.TelegramError:
        return False

    if channel.type != "channel":
        return False

    chat_member = bot.get_chat_member(chat_id=candidate, user_id=bot.id)
    if chat_member.status not in (chat_member.ADMINISTRATOR, chat_member.CREATOR):
        return False

    session = db.Session()
    if session.query(channel_model_class).filter_by(id=channel.id).count() > 0:

        if channel_model_class is ChannelToSubscribe:
            session.query(channel_model_class).get(channel.id).enabled = True
            session.commit()
            session.close()
            return True

        # already exists
        session.close()
        return False

    new_channel = channel_model_class(id=channel.id)
    session.add(new_channel)
    session.commit()
    session.close()

    return True


def delete_channel_by_instance(channel):
    session = db.Session()
    if channel.__class__ is ChannelToSubscribe:
        session.query(channel.__class__).get(channel.id).enabled = False
    else:
        session.query(channel.__class__).filter_by(id=channel.id).delete()
    session.commit()
    session.close()


def try_delete_channel(bot: Bot, candidate: str, channel_model_class):
    if candidate[0] != "@":
        candidate = "@" + candidate

    try:
        channel = bot.get_chat(chat_id=candidate)
    except err.TelegramError as e:
        return False

    if channel.type != "channel":
        return False

    session = db.Session()
    if session.query(channel_model_class).filter_by(id=channel.id).count() == 0:
        # already deleted
        session.close()
        return False

    if channel_model_class is ChannelToSubscribe:
        session.query(channel_model_class).get(channel.id).enabled = False
    else:
        session.query(channel_model_class).filter_by(id=channel.id).delete()

    session.commit()
    session.close()

    return True


def get_channels_for_subscription():
    session = db.Session()
    channels = session.query(ChannelToSubscribe).filter_by(enabled=True).all()
    session.close()
    return channels


def markup_channels_list(bot: Bot, channels: list):
    def single_channel_repr(channel):
        try:
            chat_instance = bot.get_chat(chat_id=channel.id)
        except err.Unauthorized:
            delete_channel_by_instance(channel)
            return None
        return " -- ".join(["@" + chat_instance.username, chat_instance.title])

    title = "Ссылка -- Заголовок\n"
    return title + "\n".join(filter(lambda x: x is not None, [single_channel_repr(channel) for channel in channels]))


def markup_channels_list_to_user(bot: Bot, channels: list):
    def single_channel_repr(channel):
        try:
            chat_instance = bot.get_chat(chat_id=channel.id)
        except err.Unauthorized:
            delete_channel_by_instance(channel)
            return None
        return " -- ".join(["@" + chat_instance.username, chat_instance.title])

    title = "1) Подпишитесь на все каналы\n"
    return title + "\n".join(filter(lambda x: x is not None, [single_channel_repr(channel) for channel in channels]))


def fetch_channel_to_subscribe(bot: Bot, user_data: dict):
    channels = get_channels_for_subscription()
    if len(channels) == 0:
        return None
    random.shuffle(channels)

    session = db.Session()
    for channel in channels:
        query = session.query(Subscription).filter_by(user_id=int(user_data["id"]), channel_id=channel.id)
        if query.count() == 0:
            session.close()
            return channel

    session.close()
    return None


def update_subs_count(user_id, count):
    session = db.Session()
    session.query(User).get(user_id).count = count
    session.commit()
    session.close()


def check_subscription(bot: Bot, user_data: dict, channel_id: int):
    try:
        result = bot.get_chat_member(chat_id=channel_id, user_id=user_data["id"])
    except err.TelegramError as e:
        return False
    return result.status != result.LEFT and result.status != result.KICKED


def save_subscription(user_data: dict, channel_id: int):
    session = db.Session()
    c = session.query(Subscription).filter_by(user_id=user_data["id"], channel_id=channel_id).count()
    if c == 0:
        session.add(Subscription(user_id=user_data["id"], channel_id=channel_id))
        session.commit()
        session.close()
        return True
    else:
        session.close()
        return False


def get_invitation_link(user_id):
    return f"t.me/{settings.BOT_LINK}?start={user_id}"


def give_award(user_data: dict, award: int, push_to_inviter=True):
    session = db.Session()
    user = session.query(User).get(user_data["id"])
    user.cash += award

    if push_to_inviter:
        user_referral_link = session.query(ReferralLink).get(user_data["id"])
        if user_referral_link is not None:
            inviter = user_referral_link.invited_by
            inviter.referral_cash += award // 10
            inviter.cash += award // 10

    session.commit()
    session.close()


def get_invited_users_count(user_data: dict):
    session = db.Session()
    result = session.query(ReferralLink).filter_by(invited_by_id=user_data["id"]).count()
    session.close()
    return result


def check_before_withdrawal(user_data: dict):
    session = db.Session()
    cash = session.query(User).get(user_data["id"]).cash
    session.close()
    return cash >= settings.MINIMAL_WITHDRAWAL_AMOUNT * 100


def get_all_users_count():
    session = db.Session()
    result = session.query(User).count()
    session.close()
    return result


def get_active_users_count(active_timelimit=604800):
    session = db.Session()
    activity_lower_bound = datetime.utcnow() - timedelta(seconds=active_timelimit)
    result = session.query(User).filter(User.last_activity > activity_lower_bound).count()
    session.close()
    return result


def get_referral_links_count():
    session = db.Session()
    result = session.query(ReferralLink).count()
    session.close()
    return result


def get_payment_link(sum_, order_id, merchant_id=payment_settings.MERCHANT_ID):
    base = r"https://www.free-kassa.ru/merchant/cash.php"
    hash_ = payment_utils.generate_userside_sign(order_id, sum_)
    return f"{base}?m={merchant_id}&oa={sum_}&o={order_id}&s={hash_}"


def make_new_payment(user_data: dict, amount: int):
    session = db.Session()
    new_payment = Payment(
        user_id=user_data["id"],
        amount=amount,
        accepted=False
    )
    session.add(new_payment)
    session.commit()
    payment_id = new_payment.id
    session.close()
    return payment_id


def accept_payment(payment_id):
    session = db.Session()
    payment = session.query(Payment).get(payment_id)
    if payment is None:
        session.close()
        return False
    payment.accepted = True
    session.commit()
    session.close()
    return True


def check_payment(payment_id):
    session = db.Session()
    payment = session.query(Payment).get(payment_id)
    if (payment is None) or (not payment.accepted):
        session.close()
        return None
    result = payment.amount
    session.close()
    return result


def check_is_user_verified(user_data: dict):
    session = db.Session()
    if session.query(Payment).filter_by(user_id=user_data["id"], accepted=True).count() > 1:
        session.close()
        return True
    session.close()
    return False


def set_last_bonus(user_id):
    session = db.Session()
    session.query(User).get(user_id).last_bonus = datetime.utcnow()
    session.commit()
    session.close()


def set_blocked(user_id):
    session = db.Session()
    session.query(User).get(user_id).blocked = True
    session.commit()
    session.close()


def get_adlinks():
    session = db.Session()
    adlinks = session.query(AdLink).all()
    session.close()
    return adlinks


def get_adlink_href(uuid):
    return f"https://tele.click/{settings.BOT_LINK}?start={uuid}"


def markup_adlinks(adlinks):
    def single_adlink_repr(adlink):
        return " -- ".join([str(adlink.id), f"""<a href="{get_adlink_href(adlink.uuid)}">{adlink.keyword}</a>"""])

    title = "# -- Ключевое слово (ссылки рабочие)\n"
    return title + "\n".join([single_adlink_repr(adlink) for adlink in adlinks])


def new_ad_link(keyword):
    session = db.Session()
    # try:
    adlink = AdLink(uuid=str(uuid.uuid4()), keyword=keyword)
    session.add(adlink)
    session.commit()
    result = adlink.id
    # except Exception:
    #     session.close()
    #     return None

    session.close()
    return result


def get_adlink(ident):
    session = db.Session()
    result = session.query(AdLink).get(ident)
    session.close()
    return result


def try_delete_adlink(keyword):
    session = db.Session()
    adlinks = session.query(AdLink).filter_by(keyword=keyword).all()
    if len(adlinks) == 0:
        session.close()
        return False

    for adlink in adlinks:
        session.delete(adlink)
    session.commit()
    session.close()
    return True


def increase_clicks(adlink_uuid):
    session = db.Session()
    try:
        adlink = session.query(AdLink).filter_by(uuid=adlink_uuid).one_or_none()
        adlink.clicks += 1
        session.commit()
    finally:
        session.close()


def adlinks_statistics_markup():
    def single_adlink_repr(adlink):
        return ": ".join([f"""<a href="{get_adlink_href(adlink.uuid)}">{adlink.keyword}</a>""",
                          str(adlink.users_count)])

    return "\n".join([single_adlink_repr(adlink) for adlink in get_adlinks()])


def get_count_keys():
    session = db.Session()
    result = session.query(Keys).count()
    session.close()
    return result


def try_add_keys(keys):
    session = db.Session()
    key = Keys(key=keys)
    session.add(key)
    session.commit()
    session.close()


def get_key():
    session = db.Session()
    keys = session.query(Keys).all()
    if len(keys) == 0:
        return None
    random.shuffle(keys)
    session.close()
    return keys[0]


def delete_key(key):
    session = db.Session()
    keys = session.query(Keys).filter_by(key=key).all()
    if len(keys) == 0:
        session.close()
        return False

    for key in keys:
        session.delete(key)
    session.commit()
    session.close()
    return True


def check_subs_mode(user_data):
    session = db.Session()
    result = session.query(User).get(user_data['chat_id']).channel_key
    session.close()
    return result


def set_subs_mode(user_data):
    session = db.Session()
    session.query(User).get(user_data['chat_id']).channel_key = False
    session.commit()
    session.close()


def get_files():
    all_files_in_directory = os.listdir('/tmp/')
    return all_files_in_directory


def parse_text_to_key(text):
    keys = text.split('\n')
    for key in keys:
        try_add_keys(key)


def get_count_keys_by_user(user_data):
    session = db.Session()
    result = session.query(User).get(user_data['chat_id']).sub_keys
    session.close()
    return result


def check_give_key(user_data):
    session = db.Session()
    ref_key = session.query(User).get(user_data['chat_id']).sub_keys
    ref_count = get_invited_users_count(user_data)
    key_away = session.query(User).get(user_data['chat_id']).keys_away
    if ref_count % 3 == 0 and ref_count != 0:
        session.query(User).get(user_data['chat_id']).sub_keys += 1
        if ref_count * ref_key > key_away:
            return True
        else:
            return False
    else:
        return False

