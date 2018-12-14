from telegram import Update, Message
from telegram.ext import DispatcherHandlerStop
import telegram.error

from utils import *
from user_actions import *
from admin_actions import *
from broadcasting import post_constructor_first_step
import withdrawal
from random import choice


def start_callback(bot: Bot, update: Update, user_data: dict, args: list):
    if len(args) > 0:
        is_new = prepare_user_data(update, user_data, int(args[0]))
    else:
        is_new = prepare_user_data(update, user_data)

    command = None
    entities = Message.parse_entities(update.message, ["bot_command"])
    for entity in entities:
        command = entities[entity]
        break

    if command is None:
        raise RuntimeError("Something goes wrong")
    command = command[1:]
    is_new = True
    if command == "start":
        if is_new:
            primary_instructions(bot, user_data)
        else:
            start(bot, user_data)



def command_callback(bot: Bot, update: Update, user_data: dict):
    prepare_user_data(update, user_data)
    new_state = None
    command = None
    entities = Message.parse_entities(update.message, ["bot_command"])
    for entity in entities:
        command = entities[entity]
        break

    if command is None:
        assert "Something goes wrong"
    command = command[1:]

    if command == "admin":
        session = db.Session()
        permissions_level = session.query(User).get(int(user_data["id"])).permissions
        session.close()
        if permissions_level >= PermissionsLevels.ADMIN:
            new_state = admin_welcome(bot, user_data)


    if new_state is not None:
        set_state(user_data["id"], user_data, new_state)


def text_message_callback(bot: Bot, update: Update, user_data: dict):
    prepare_user_data(update, user_data)
    new_state = None

    if type(user_data["node"]) is not int:
        user_data["node"] = user_data["node"].result()

    if user_data["node"] >= 0:
        if update.message.text == "❓ Помощь":
            help_msg(bot, user_data)
        elif update.message.text == "🗝 Ключи":
            earn(bot, user_data)
        elif update.message.text == "🔥Игры с 90% скидкой 🔥":
            keys_site(bot, user_data)
        elif update.message.text == "👥 Друзья":
            referrals(bot, user_data)
        elif update.message.text == "Прочитал ✅":
            start(bot, user_data)
    elif user_data["node"] == -1:
        if update.message.text == "Статистика":
            new_state = admin_statistics(bot, user_data)
        elif update.message.text == "Рассылка":
            new_state = post_constructor_first_step(bot, user_data)
        elif update.message.text == "Задания":
            new_state = channels_management(bot, user_data)
        elif update.message.text == "Выход из админки":
            new_state = start(bot, user_data).result()
        elif update.message.text == "Рекламная рефералка":
            new_state = ad_link_menu(bot, user_data)
        elif update.message.text == "Загрузить ключи":
            new_state = ad_keys(bot, user_data)
    elif user_data["node"] == -2:
        if update.message.text == "Подписка на канал":
            new_state = channels_for_subscription_list(bot, user_data)
        elif update.message.text == "Назад":
            new_state = admin_welcome(bot, user_data)
    elif user_data["node"] == -6:
        if update.message.text == "Добавить канал":
            new_state = add_channel_for_subscription_first_step(bot, user_data)
        elif update.message.text == "Удалить канал":
            new_state = delete_channel_for_subscription_first_step(bot, user_data)
        elif update.message.text == "Назад":
            new_state = channels_management(bot, user_data)
    elif user_data["node"] == -7:
        if update.message.text == "Отмена":
            new_state = channels_for_subscription_list(bot, user_data)
        else:
            #  try to parse a channel link
            if try_add_channel(bot, update.message.text, ChannelToSubscribe):
                new_state = channel_added_succsessfully(bot, user_data, channels_for_subscription_list)
            else:
                new_state = error_during_channel_adding(bot, user_data, add_channel_for_subscription_first_step)
    elif user_data["node"] == -8:
        if update.message.text == "Отмена":
            new_state = channels_for_subscription_list(bot, user_data)
        else:
            if try_delete_channel(bot, update.message.text, ChannelToSubscribe):
                new_state = channel_deleted_succsessfully(bot, user_data, channels_for_subscription_list)
            else:
                new_state = error_during_channel_deleting(bot, user_data, delete_channel_for_subscription_first_step)
    # elif user_data["node"] == -9:
    #     if update.message.text == "Назад":
    #         new_state = admin_welcome(bot, user_data)
    #     elif update.message.text == "Добавить":
    #          new_state = add_ref_link_for_promoution_first_step(bot, user_data)
    #     elif update.message.text == "Удалить":
    #         new_state = delete_ref_link_for_promoution_first_step(bot, user_data)
    elif user_data["node"] == -10:
        if update.message.text == "Добавить":
            new_state = add_ad_link(bot, user_data)
        elif update.message.text == "Удалить":
            new_state = delete_ad_link(bot, user_data)
        elif update.message.text == "Назад":
            new_state = admin_welcome(bot, user_data)
    elif user_data["node"] == -11:
        if update.message.text == "Назад":
            new_state = ad_link_menu(bot, user_data)
        else:
            adlink = new_ad_link(update.message.text)
            if adlink is not None:
                new_state = ad_link_added(bot, user_data, adlink)
            else:
                new_state = ad_link_menu(bot, user_data)
    elif user_data["node"] == -12:
        if update.message.text == "Назад":
            new_state = ad_link_menu(bot, user_data)
        else:
            if try_delete_adlink(update.message.text):
                new_state = ad_link_deleted(bot, user_data)
            else:
                new_state = error_during_adlink_deleting(bot, user_data)
    elif user_data["node"] == -16:
        if update.message.text == "Отмена":
            new_state = admin_welcome(bot, user_data)
        elif update.message.text:
            parse_text_to_key(update.message.text)
            new_state = kek(bot, user_data, update.message.text)
        else:
            #try_add_keys()
            new_state = admin_welcome(bot, user_data)

    if new_state is not None:
        set_state(user_data["id"], user_data, new_state)
    raise DispatcherHandlerStop


def callback_query_callback(bot: Bot, update: Update, user_data: dict):
    prepare_user_data(update, user_data)
    delete_keyboard = True
    answer_callback = True

    if type(user_data["node"]) is not int:
        user_data["node"] = user_data["node"].result()

    if user_data["node"] >= 0:
        args = update.callback_query.data.split('?')

        if args[0] == "subscribe":
            subscribe_channel(bot, user_data)
        elif args[0] == "invite":
            referrals(bot, user_data)
        elif args[0] == "earn_more":
            earn(bot, user_data)
        elif args[0] == "get_money":
            channels = get_channels_for_subscription()
            count = 0
            for channel in channels:
                channel_id = channel.id
                if check_subscription(bot, user_data, channel_id):
                    # if save_subscription(user_data, channel_id):
                    count += 1
                    # else:
                    #     answer_callback = False
            update_subs_count(user_data['chat_id'], count)
            if count == len(channels):
                give_key(bot, user_data)
            else:
                delete_keyboard = False
                subscription_not_completed(bot, user_data)
            # if check_subscription(bot, user_data, channel_id):
            #     if save_subscription(user_data, channel_id):
            #         task_completed(bot, user_data, settings.SUBSCRIPTION_BONUS * 100)
            #     else:
            #         answer_callback = False
            # else:
            #     delete_keyboard = False
            #     subscription_not_completed(bot, user_data)
        else:
            have_processed, delete_keyboard = withdrawal.processor.process(bot, update, user_data)

    if delete_keyboard:
        try:
            bot.edit_message_reply_markup(message_id=update.callback_query.message.message_id,
                                          chat_id=user_data["chat_id"])
        except telegram.error.BadRequest:
            # it's okay. Сообщение было изменено ранее и/и
            pass

    if answer_callback:
        try:
            bot.answer_callback_query(update.callback_query.id)
        except telegram.error.BadRequest:
            # it's okay too. Данный callback уже был обработан
            pass
    raise DispatcherHandlerStop
