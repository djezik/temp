from telegram import ReplyKeyboardMarkup, ParseMode

from queued_bot import Bot
from utils import get_all_users_count, get_active_users_count, get_referral_links_count, \
    markup_channels_list, get_channels_for_subscription, get_adlinks, markup_adlinks, get_adlink, get_adlink_href, \
    adlinks_statistics_markup, get_count_keys


def admin_welcome(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Добро пожаловать в интерфейс администратора, выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            [["Статистика"],
             ["Рассылка", 'Задания'],
             ["Рекламная рефералка"],
             ["Загрузить ключи"],
             ["Выход из админки"]],
            resize_keyboard=True
        )
    )
    return -1


def admin_statistics(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Всего пользователей: {all_users}\nАктивных (за прошедшую неделю): {active}\n"
             "Приглашенных через систему рефералов: {ref_count}\n"
             "Ключей осталось: {keys_active}\nКлючей раздали: {keys_gets}".format(
            all_users=get_all_users_count(),
            active=get_active_users_count(),
            ref_count=get_referral_links_count(),
            keys_active=get_count_keys(),
            keys_gets=0) + "\n\nРекламные ссылки:\n" + adlinks_statistics_markup(),
        parse_mode=ParseMode.HTML
    )
    return -1

def ad_link_menu(bot: Bot, user_data: dict):
    adlinks = get_adlinks()
    if len(adlinks) == 0:
        text = "Список реферальных рекламных ссылок пуст"
    else:
        text = markup_adlinks(adlinks)

    bot.send_message(
        chat_id=user_data["chat_id"],
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            [["Добавить"],
             ["Удалить"],
             ["Назад"]],
            resize_keyboard=True
        )
    )
    return -10


def add_ad_link(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Введите ключевое слово:",
        reply_markup=ReplyKeyboardMarkup(
            [["Назад"]],
            resize_keyboard=True,
        )
    )
    return -11


def ad_link_added(bot: Bot, user_data: dict, adlink_id):
    adlink = get_adlink(adlink_id)
    href = get_adlink_href(adlink.uuid)
    bot.send_message(
        chat_id=user_data["chat_id"],
        text=f'<a href="{href}">{adlink.keyword}</a>\n'
             f'"Сырая" ссылка: {href}',
        parse_mode=ParseMode.HTML,
    )
    return admin_welcome(bot, user_data)


def delete_ad_link(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Удаление ссылки. Введите ключевое слово:",
        reply_markup=ReplyKeyboardMarkup(
            [["Назад"]],
            resize_keyboard=True,
        )
    )
    return -12


def ad_link_deleted(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Ссылка удалена."
    )
    return ad_link_menu(bot, user_data)


def error_during_adlink_deleting(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Ссылок с таким ключевым словом не найдено. Проверьте правильность написания."
    )
    return -12


def channels_management(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Управление заданиями. Выберите тип задания:",
        reply_markup=ReplyKeyboardMarkup([
            ["Подписка на канал"],
            ["Назад"]
        ], resize_keyboard=True)
    )
    return -2


def channels_for_subscription_list(bot: Bot, user_data: dict):
    channels = get_channels_for_subscription()
    if len(channels) == 0:
        bot.send_message(
            chat_id=user_data["chat_id"],
            text="Список каналов для подписки пуст.",
            reply_markup=ReplyKeyboardMarkup([
                ["Добавить канал"],
                ["Назад"]
            ], resize_keyboard=True)
        )
    else:
        bot.send_message(
            chat_id=user_data["chat_id"],
            text="Каналы для подписки:\n\n"
                 "{channels_repr}".format(channels_repr=markup_channels_list(bot, channels)),
                 reply_markup=ReplyKeyboardMarkup([
                ["Добавить канал"],
                ["Удалить канал"],
                ["Назад"],
            ], resize_keyboard=True)
        )

    return -6


def add_channel_for_subscription_first_step(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Отправьте сюда адрес канала (@example или просто example)",
        reply_markup=ReplyKeyboardMarkup([
            ["Отмена"]
        ], resize_keyboard=True)
    )
    return -7


def channel_added_succsessfully(bot: Bot, user_data: dict, next_callable):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Канал успешно добавлен.",
    )
    return next_callable(bot, user_data)


def error_during_channel_adding(bot: Bot, user_data: dict, next_callable):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Ошибка при добавлении канала. Возможные причины: канал не существует, ссылка введена "
             "неправильно, он уже был добавлен ранее или бот не имеет прав администратора в канале. Попробуйте снова:"
    )
    return next_callable(bot, user_data)


def delete_channel_for_subscription_first_step(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Отправьте сюда адрес канала (@example или просто example)",
        reply_markup=ReplyKeyboardMarkup([
            ["Отмена"]
        ], resize_keyboard=True)
    )
    return -8


def channel_deleted_succsessfully(bot: Bot, user_data: dict, next_callable):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Канал успешно удален.",
    )
    return next_callable(bot, user_data)


def error_during_channel_deleting(bot: Bot, user_data: dict, next_callable):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Ошибка при удалении канала. Возможные причины: канал не существует, ссылка введена "
             "неправильно или он уже был удален ранее. Попробуйте снова:"
    )
    return next_callable(bot, user_data)


def ad_keys(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Отправьте боту файл с ключами",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)
    )
    return -16


def kek(bot: Bot, user_data: dict, text):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text='Не работает или работает? {text}'.format(text=repr(text))
    )
