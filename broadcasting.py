import json
from datetime import datetime, timedelta, time, timezone
import time as tm
import copy
import logging
import traceback
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, ReplyKeyboardMarkup, ParseMode
from telegram.ext import MessageHandler, Filters, CallbackQueryHandler, run_async, DispatcherHandlerStop
import telegram.error as err
from sqlalchemy.exc import OperationalError

from bot import dispatcher
import db
from models import Post, User
from queued_bot import Bot
from utils import prepare_user_data, set_state, set_blocked
from admin_actions import admin_welcome


def prepare_constructor_handlers(user_data: dict):
    if user_data.get("handler") is None:
        user_data["handler"] = MessageHandler(
            Filters.chat(chat_id=user_data["chat_id"]),
            constructor_callback,
            pass_user_data=True,
            pass_job_queue=True
        )
        dispatcher.add_handler(user_data["handler"], group=-1)

    if user_data.get("callback_handler") is None:
        user_data["callback_handler"] = CallbackQueryHandler(
            callback_query_constructor_callback,
            pass_user_data=True
        )
        dispatcher.add_handler(user_data["callback_handler"], group=-1)


def destruct_constructor_handlers(user_data: dict):
    dispatcher.remove_handler(user_data["handler"], group=-1)
    del user_data["handler"]
    dispatcher.remove_handler(user_data["callback_handler"], group=-1)
    del user_data["callback_handler"]


def save_post_draft(user_data: dict, jsoned_message, jsoned_reply_markup=None):
    if jsoned_reply_markup is None and jsoned_message is None:
        raise ValueError("jsoned_message and jsoned_reply_markup can't be None together")

    session = db.Session()

    if user_data.get("post_id") is not None:
        post = session.query(Post).get(user_data["post_id"])
        if jsoned_message is not None:
            post.data = jsoned_message
        post.reply_markup_data = jsoned_reply_markup
        session.commit()
    else:
        if jsoned_message is not None:
            new_post = Post(draft=True, data=jsoned_message, reply_markup_data=jsoned_reply_markup)
            session.add(new_post)
            session.commit()
            user_data["post_id"] = new_post.id
        else:
            session.close()
            raise RuntimeError("Try to make new Post in db with empty jsoned_message")

    session.close()


def save_post(user_data: dict, delay: int):
    date_time_to_broadcast = datetime.utcnow() + timedelta(minutes=delay)
    session = db.Session()
    post = session.query(Post).get(user_data["post_id"])
    post.draft = False
    post.time_to_publish = date_time_to_broadcast
    session.commit()
    session.close()


def delete_post(user_data: dict):
    if user_data.get("post_id") is not None:
        session = db.Session()
        session.query(Post).filter_by(id=user_data["post_id"]).delete()
        session.commit()
        session.close()
        del user_data["post_id"]


def de_json_inline_keyboard_markup(obj: dict):
    assert type(obj) == dict
    if obj.get("inline_keyboard") is not None:
        markup = []
        assert type(obj["inline_keyboard"]) == list
        for line in obj["inline_keyboard"]:
            assert type(line) == list
            markup.append([InlineKeyboardButton(**button) for button in line])

        return InlineKeyboardMarkup(markup)
    else:
        return None


def parse_post_to_send(post_id):
    session = db.Session()
    post_instance = session.query(Post).get(post_id)
    session.close()
    if post_instance.data is None:
        return None, None, None
    message = Message.de_json(data=json.loads(post_instance.data), bot=None)
    reply_markup = None
    if post_instance.reply_markup_data is not None:
        reply_markup = de_json_inline_keyboard_markup(json.loads(post_instance.reply_markup_data))

    kwargs = {}
    method = None
    if message.audio is not None:
        method = "audio"
        kwargs["audio"] = message.audio.file_id
        kwargs["duration"] = message.audio.duration
        kwargs["performer"] = message.audio.performer
        kwargs["title"] = message.audio.title
        if message.audio.thumb is not None:
            kwargs["thumb"] = message.audio.thumb.file_id
    elif message.document is not None:
        method = "document"
        kwargs["document"] = message.document.file_id
        if message.document.thumb is not None:
            kwargs["thumb"] = message.document.thumb.file_id
    elif message.video is not None:
        method = "video"
        kwargs["video"] = message.video.file_id
        kwargs["duration"] = message.video.duration
        kwargs["width"] = message.video.width
        kwargs["height"] = message.video.height
        if message.video.thumb is not None:
            kwargs["thumb"] = message.video.thumb.file_id
    elif message.animation is not None:
        method = "animation"
        kwargs["animation"] = message.animation.file_id
        kwargs["duration"] = message.animation.duration
        kwargs["width"] = message.animation.width
        kwargs["height"] = message.animation.height
        if message.animation.thumb is not None:
            kwargs["thumb"] = message.animation.thumb.file_id
    elif message.voice is not None:
        method = "voice"
        kwargs["voice"] = message.voice.file_id
        kwargs["duration"] = message.voice.duration
    elif message.video_note is not None:
        method = "video_note"
        kwargs["video_note"] = message.video_note.file_id
        kwargs["duration"] = message.video_note.duration
        kwargs["length"] = message.video_note.length
        if message.video_note.thumb is not None:
            kwargs["thumb"] = message.video_note.thumb.file_id
    elif message.location is not None:
        method = "location"
        kwargs["latitude"] = message.location.latitude
        kwargs["longitude"] = message.location.longitude
    elif message.venue is not None:
        method = "venue"
        kwargs["latitude"] = message.venue.location.latitude
        kwargs["longitude"] = message.venue.location.longitude
        kwargs["title"] = message.venue.title
        kwargs["address"] = message.venue.address
        kwargs["foursquare_id"] = message.venue.foursquare_id
        kwargs["foursquare_type"] = message.venue.foursquare_type
    elif message.contact is not None:
        method = "contact"
        kwargs["phone_number"] = message.contact.phone_number
        kwargs["first_name"] = message.contact.first_name
        kwargs["last_name"] = message.contact.last_name
        kwargs["vcard"] = message.contact.vcard
    elif len(message.photo) > 0:
        method = "photo"
        kwargs["photo"] = sorted(message.photo, key=lambda x: x.width * x.height, reverse=True)[0].file_id
    elif message.sticker is not None:
        method = "sticker"
        kwargs["sticker"] = message.sticker.file_id
    elif message.text is not None:
        method = "message"
        kwargs["text"] = message.text
    else:
        raise NotImplementedError("Unsupported post type")

    if message.caption is not None:
        kwargs["caption"] = message.caption

    return "send_" + method, kwargs, reply_markup


def make_reply_markup(text):
    try:
        lines = text.splitlines()
        blanks = [tuple(x.strip() for x in line.split("-")) for line in lines]
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(text=blank[0], url=blank[1])] for blank in blanks
        ])
    except Exception:
        return None


@run_async
def broadcast_post(bot, user_data, method, kwargs, reply_markup):
    session = db.Session()
    users = session.query(User).filter_by(blocked=False).all()
    session.close()

    successful_msgs = 0
    for user in users:
        try:
            getattr(bot, method)(
                chat_id=user.id,
                reply_markup=reply_markup,
                **kwargs
            )
            successful_msgs += 1
        except err.Unauthorized:
            try:
                set_blocked(user.id)
            except Exception:
                pass
        except err.RetryAfter as e:
            tm.sleep(e.retry_after + 1.0)
        except err.TelegramError:
            pass
        tm.sleep(0.2)

    bot.send_message(
        chat_id=user_data["chat_id"],
        text=f"Рассылка успешно выполнена!\nРазослано {successful_msgs} сообщений",
    )

    session = db.Session()
    session.query(Post).filter_by(id=user_data["post_id"]).delete()
    session.commit()
    session.close()


def delayed_broadcasting_job_callback(bot, job):
    broadcast_post(bot, *job.context)


def parse_delay(delay: str):
    components = delay.split(" ")
    if len(components) % 2 != 0:
        return None

    result_minutes = 0

    for i in range(0, len(components), +2):
        try:
            num = int(components[i].strip())
        except ValueError:
            return None
        label = components[i + 1].strip().lower()
        if (len(label) != 1) or (label not in ("д", "м", "ч")):
            return None

        if label == "д":
            result_minutes += num * 24 * 60
        elif label == "ч":
            result_minutes += num * 60
        else:
            result_minutes += num

    return result_minutes


def empty_msg(bot: Bot, user_data: dict, next_state, additional_text=""):
    assert type(additional_text) == str

    bot.send_message(
        chat_id=user_data["chat_id"],
        text=f"< < Пустое сообщение > >\n{additional_text}"
    )
    return next_state


def post_preview(bot: Bot, user_data: dict, settings_mode=True):
    method, kwargs, reply_markup = None, None, None
    if user_data.get("post_id") is not None:
        method, kwargs, reply_markup = parse_post_to_send(user_data["post_id"])

    if method is None:
        return empty_msg(bot, user_data, -10)

    if settings_mode:
        if reply_markup is None:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Добавить url-кнопки", callback_data="add_buttons")]
            ])
        else:
            reply_markup.inline_keyboard.append(
                [InlineKeyboardButton(text="Удалить url-кнопки", callback_data="del_buttons")]
            )

    getattr(bot, method)(
        chat_id=user_data["chat_id"],
        reply_markup=reply_markup,
        **kwargs
    )
    return -10


def adding_inline_keyboard_hint(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Чтобы добавить inline-клавиатуру к сообщению, отправьте ссылки в следующем формате:\n"
             "Название кнопки 1 - ссылка 1\n"
             "Название кнопки 2 - ссылка 2\n"
             "И так далее...\n\n"
             "Например:\n"
             "YouTube - https://youtube.com/\n",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="Отмена", callback_data="cancel")]])
    )
    return -11


def error_during_buttons_adding(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Ошибка при добавлении кнопок. Проверьте соблюдение формата и/или корректность ссылок\n\n"
    )
    return -11


def sending_post_settings(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Сообщение готово к публикации, хотите начать рассылку прямо сейчас или отложить?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="Опубликовать", callback_data="publish"),
             InlineKeyboardButton(text="Отложить", callback_data="delay")],
            [InlineKeyboardButton(text="<< Назад", callback_data="go_back")]
        ])
    )
    return -12


def broadcast_post_hint(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Рассылка началась или начнется в запланированное время. Ввиду ограничения telegram на"
             "рассылку сообщений ботами, процесс может проходить не так быстро, как вы ожидаете. После"
             "окончания рассылки вы получите уведомление."
    )
    return admin_welcome(bot, user_data)


def delay_post_broadcasting(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="На сколько задержать рассылку поста?\n"
             "Отправьте сообщение в формате:\n"
             "[% Количество дней % д] [% Колисество часов % ч] [% Количество минут % м]\n"
             "Например: 2 д 3 ч 30 м -- задержка на 2 дня и 3,5 часа\n"
             "90 м -- задержка на 90 минут (эквивалент 1 ч 30 м)"
    )
    return -13


def error_during_delay_parsing(bot: Bot, user_data: dict):
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Пожалуйста, соблюдайте формат:\n"
             "[% Количество дней % д] [% Колисество часов % ч] [% Количество минут % м]\n"
    )
    return -13


def constructor_callback(bot: Bot, update: Update, job_queue, user_data: dict):
    prepare_user_data(update, user_data)

    new_state = None
    if user_data["node"] in (-9, -10, -12):
        if update.message.text is not None:
            if update.message.text == "Отменить":
                delete_post(user_data)
                destruct_constructor_handlers(user_data)
                new_state = admin_welcome(bot, user_data)
            elif update.message.text == "Очистить":
                delete_post(user_data)
                new_state = post_constructor_first_step(bot, user_data)
            elif update.message.text == "Предпросмотр":
                new_state = post_preview(bot, user_data, False)
            elif update.message.text == "Далее":
                if user_data.get("post_id") is not None:
                    new_state = sending_post_settings(bot, user_data)
                else:
                    new_state = empty_msg(bot, user_data, -9, "Невозможно разослать пустое сообщение")
            else:
                save_post_draft(user_data, update.message.to_json())
                new_state = post_preview(bot, user_data)
        else:
            save_post_draft(user_data, update.message.to_json())
            new_state = post_preview(bot, user_data)
    elif user_data["node"] == -11:
        reply_markup = make_reply_markup(update.message.text)
        if reply_markup is not None:
            save_post_draft(user_data, None, reply_markup.to_json())
            new_state = post_preview(bot, user_data)
        else:
            new_state = error_during_buttons_adding(bot, user_data)
    elif user_data["node"] == -13:
        delay = parse_delay(update.message.text)
        if delay is not None:
            job_queue.run_once(
                callback=delayed_broadcasting_job_callback,
                when=delay*60,  # from minutes to seconds
                context=(copy.deepcopy(user_data), *parse_post_to_send(user_data["post_id"]))
            )
            save_post(user_data, delay)
            del user_data["post_id"]
            destruct_constructor_handlers(user_data)
            new_state = broadcast_post_hint(bot, user_data)
        else:
            new_state = error_during_delay_parsing(bot, user_data)

    if new_state is not None:
        set_state(user_data["id"], user_data, new_state)
    raise DispatcherHandlerStop


def callback_query_constructor_callback(bot: Bot, update: Update, user_data: dict):
    prepare_user_data(update, user_data)

    delete_keyboard = True
    new_state = None
    if user_data["node"] == -10:
        if update.callback_query.data == "add_buttons":
            new_state = adding_inline_keyboard_hint(bot, user_data)
        elif update.callback_query.data == "del_buttons":
            save_post_draft(user_data, update.callback_query.message.to_json())
            new_state = post_preview(bot, user_data)
    elif user_data["node"] == -11:
        if update.callback_query.data == "cancel":
            new_state = post_preview(bot, user_data)
    elif user_data["node"] == -12:
        if update.callback_query.data == "publish":
            save_post(user_data, 0)
            broadcast_post(bot, copy.deepcopy(user_data), *parse_post_to_send(user_data["post_id"]))
            del user_data["post_id"]
            destruct_constructor_handlers(user_data)
            new_state = broadcast_post_hint(bot, user_data)
        elif update.callback_query.data == "delay":
            new_state = delay_post_broadcasting(bot, user_data)
        elif update.callback_query.data == "go_back":
            new_state = post_preview(bot, user_data)

    if new_state is not None:
        set_state(user_data["id"], user_data, new_state)
        if delete_keyboard:
            bot.edit_message_reply_markup(message_id=update.callback_query.message.message_id,
                                          chat_id=user_data["chat_id"])

    bot.answer_callback_query(update.callback_query.id)
    raise DispatcherHandlerStop


def post_constructor_first_step(bot: Bot, user_data: dict):
    prepare_constructor_handlers(user_data)
    bot.send_message(
        chat_id=user_data["chat_id"],
        text="Отправьте боту то, что хотите опубликовать. Это может быть всё, что угодно --"
             "текст, фото, видео, даже стикеры. Однако, из-за ограничений telegram в сообщении может быть"
             "не более одного вложения (фото + текст, видео + текст, и т. д.), причем в некоторых случаях"
             "(стикеры) может быть ТОЛЬКО вложение, без текста.",
        reply_markup=ReplyKeyboardMarkup([
            ["Очистить", "Предпросмотр"],
            ["Отменить", "Далее"],
        ], resize_keyboard=True)
    )
    return -9


def load_posts_from_db(job_queue):
    session = db.Session()
    sheduled_posts = session.query(Post).filter_by(draft=False).all()
    session.close()

    for post in sheduled_posts:
        delay = post.time_to_publish - datetime.utcnow()
        if delay.total_seconds() < 0:
            delay = timedelta(seconds=0)

        job_queue.run_once(
            callback=delayed_broadcasting_job_callback,
            when=delay.total_seconds(),
            context=(
                {
                    "chat_id": json.loads(post.data)["chat"]["id"],
                    "post_id": post.id
                },
                *parse_post_to_send(post.id)
            )
        )


def prepare_daily_job(job_queue):
    utc = datetime(2018, 1, 15, 1, 15) - timedelta(seconds=10800)
    localtz = utc - timedelta(seconds=tm.timezone)
    #job_queue.run_daily(weekly_bonus, time=localtz.time())
