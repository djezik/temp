import time

from telegram import ReplyKeyboardMarkup, ParseMode
from telegram.ext import run_async, JobQueue, Job

from settings import *
from queued_bot import Bot
from bot import job_queue#, view_post_service
from utils import *


@run_async
def primary_instructions(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="https://telegra.ph/Osnovnye-voprosy-11-05",
        reply_markup=ReplyKeyboardMarkup([["Прочитал ✅"]], True)
    )


@run_async
def start(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Выбери пункт меню:",
        reply_markup=ReplyKeyboardMarkup([["🗝 Ключи", "❓ Помощь"], ["🔥Игры с 90% скидкой 🔥"]],
                                         resize_keyboard=True)
    )
    return 0


@run_async
def help_msg(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="""https://telegra.ph/Osnovnye-voprosy-11-05""",
        parse_mode=ParseMode.HTML
    )


@run_async
def earn(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Бесплатные ключи за подписки на каналы и за приглашенных друзей",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"➕ Подписаться на каналы", callback_data="subscribe")],
            [InlineKeyboardButton(f"👥 Пригласить друзей", callback_data="invite")],
        ])
    )


@run_async
def earn_more(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Хочешь заработать ещё больше?\n"
             "Приглашай людей по своей ссылке:\n"
             "{link} и получи за каждого друга <b>3$ + 10%</b> от его дохода.".format(
            link=get_invitation_link(user_data["id"])
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Заработать ещё", callback_data="earn_more")]
        ]),
        parse_mode=ParseMode.HTML
    )


@run_async
def subscribe_channel(bot: Bot, user_data: dict):
    channel = fetch_channel_to_subscribe(bot, user_data)
    channels = get_channels_for_subscription()
    if len(channels) == 0:
        bot.send_message(
            chat_id=user_data["chat_id"],
            text="Нет доступных для подписки каналов. Попробуйте позже",
        )
        earn_more(bot, user_data)
    elif not check_subs_mode(user_data):
        bot.send_message(
            chat_id=user_data['chat_id'],
            text="Вы уже получили ключ за подписку на каналы. Попробуйте позже"
        )
    else:
        task_text = "Задание:\n {channels_repr}\n" \
                    "2) Возвращайтесь сюда и получите вознаграждение.".format(channels_repr=markup_channels_list_to_user(bot, channels))
        bot.send_message(
            chat_id=user_data["chat_id"],
            text=task_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text="Получить награду",
                    callback_data="get_money",
                )],
            ])
        )


@run_async
def referrals(bot: Bot, user_data: dict):
    link = get_invitation_link(user_data["id"])
    if check_give_key(user_data):
        bot.send_message(
            chat_id=user_data["chat_id"],
            text="Получай ключ за каждых 3-х приглашенных друзей!\n\nОтправьте другу ссылку\n{link}\n\n"
                 "Приглашено пользователей: {invited}\n"
                 "Ключей получено: {keys}".format(link=link,
                                                  invited=get_invited_users_count(user_data),
                                                  keys=get_count_keys_by_user(user_data)),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                text='Получить ключ',
                callback_data=give_key(bot, user_data),
            )]]),
            parse_mode=ParseMode.HTML,
        )
    else:
        bot.send_message(
            chat_id=user_data["chat_id"],
            text="Получай ключ за каждых 3-х приглашенных друзей!\n\nОтправьте другу ссылку\n{link}\n\n"
                 "Приглашено пользователей: {invited}\n"
                 "Ключей получено: {keys}".format(link=link,
                                                  invited=get_invited_users_count(user_data),
                                                  keys=get_count_keys_by_user(user_data)),
            parse_mode=ParseMode.HTML,
        )


@run_async
def subscription_not_completed(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="❌ Вы не выполнили задание"
    )


@run_async
def keys_site(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data['chat_id'],
        text='Переходи на сайт и забирай ключи со скидкой 90 %',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text='Жми', url='http://slivkeys.ru/')]])
    )

#view_post_service.set_task_completed_callback(task_completed)


@run_async
def give_key(bot: Bot, user_data: dict):
    key = get_key()
    bot.send_message(
        chat_id=user_data['chat_id'],
        text='Поздравляем, вы выполнили задание, ваш ключ: {key}'.format(key=key.key)
    )
    delete_key(key.key)
    set_subs_mode(user_data)


