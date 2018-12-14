from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from callbacks import *

start_handler = CommandHandler("start", start_callback, pass_user_data=True, pass_args=True)
admin_handler = CommandHandler("admin", command_callback, pass_user_data=True)
message_handler = MessageHandler(Filters.text, text_message_callback, pass_user_data=True)
callback_query_handler = CallbackQueryHandler(callback_query_callback, pass_user_data=True)

all_handlers = (
    start_handler,
    admin_handler,
    message_handler,
    callback_query_handler,
)
