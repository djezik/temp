from telegram.utils.request import Request
from telegram.ext.messagequeue import MessageQueue
from telegram.ext import Updater

from settings import REQUEST_KWARGS, TOKEN
from queued_bot import Bot


if REQUEST_KWARGS is not None:
    request = Request(con_pool_size=16, **REQUEST_KWARGS)
else:
    request = Request(con_pool_size=16)

bot = Bot(
    token=TOKEN,
    mqueue=MessageQueue(
        all_burst_limit=26,
        all_time_limit_ms=1100
    ),
    request=request
)

updater = Updater(bot=bot, workers=16)
dispatcher = updater.dispatcher
job_queue = updater.job_queue
