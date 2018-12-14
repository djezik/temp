import logging
import os
import time

from telegram import TelegramError

from bot import updater, dispatcher, bot
import handlers
import db
import models
from broadcasting import load_posts_from_db, prepare_daily_job
from admin_actions import admin_welcome
from settings import TOKEN


def cleanup_db():
    session = db.Session()

    session.query(models.Post).filter_by(draft=True).delete()
    session.commit()

    chats_in_broadcasting_states = session.query(models.ChatState).filter(
        models.ChatState.node <= -9,
        models.ChatState.node >= -13
    ).all()
    for chat_state in chats_in_broadcasting_states:
        try:
            bot.send_message(
                chat_id=chat_state.id,
                text="Сервер был перезапущен :("
            )
            chat_state.node = admin_welcome(bot, {"chat_id": chat_state.id})
        except TelegramError:
            pass
    session.commit()
    session.close()


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

cleanup_db()

load_posts_from_db(updater.job_queue)
prepare_daily_job(updater.job_queue)

for handler in handlers.all_handlers:
    dispatcher.add_handler(handler)

# updater.start_polling()
updater.start_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", "443")),
    url_path=TOKEN
)
bot.set_webhook(url="https://li465-188.members.linode.com/" + TOKEN)

while True:
    logging.info("Updates in queue: {}".format(updater.update_queue.qsize()))
    logging.info("Forwarding next time: {}".format(bot.forwarding_next_time))
    time.sleep(2.0)

# updater.idle()
