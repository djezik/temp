import functools
from threading import Lock, get_ident
from time import perf_counter, sleep
import datetime
import logging

import telegram.bot
from telegram.ext import messagequeue
import telegram.error as err


SINGLE_MESSAGE_INTERVAL = 1.1


def unpromise(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        return method(self, *args, **kwargs).result()
    return wrapped


def chat_locking(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            chat_id = int(kwargs.get("chat_id"))
            if chat_id is None:
                try:
                    chat_id = int(args[0])
                except IndexError:
                    raise NotImplementedError("@user_locking decorator can be used only with methods which"
                                              "get chat_id arg")
        except ValueError:
            raise ValueError("chat_id must be castable to int")

        with self._global_lock:
            try:
                lock = self._users_locks[chat_id]
            except KeyError:
                lock = Lock()
                self._users_locks[chat_id] = lock

        with lock:
            timestamp = self.users_last_query.get(chat_id, 0.0)
            current_time = perf_counter()
            if current_time - timestamp < SINGLE_MESSAGE_INTERVAL:
                time_to_sleep = SINGLE_MESSAGE_INTERVAL - (current_time - timestamp)
                sleep(time_to_sleep)

            try:
                promise = method(self, *args, **kwargs)
                result = promise.result()
            except err.RetryAfter as e:
                # :(
                raise e
            finally:
                self.users_last_query[chat_id] = perf_counter()

        return result

    return wrapped


class Bot(telegram.bot.Bot):
    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
        super(Bot, self).__init__(*args, **kwargs)
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or messagequeue.MessageQueue()
        self.users_last_query = {}  # dict of timestamps
        self._users_locks = {}  # dict of Locks
        self._global_lock = Lock()
        self.forwarding_next_time = None

    def cleanup_old_timestamps(self):
        # TODO
        raise NotImplementedError()

    # @chat_locking
    @unpromise
    @messagequeue.queuedmessage
    def send_message(self, *args, **kwargs):
        logging.info("native send message method called")
        logging.info("Current Message Queue size: {}".format(
            self._msg_queue._all_delayq._queue.qsize()
        ))
        return super(Bot, self).send_message(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_audio(self, *args, **kwargs):
        return super(Bot, self).send_audio(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_contact(self, *args, **kwargs):
        return super(Bot, self).send_contact(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_document(self, *args, **kwargs):
        return super(Bot, self).send_document(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_photo(self, *args, **kwargs):
        return super(Bot, self).send_photo(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_video(self, *args, **kwargs):
        return super(Bot, self).send_video(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_voice(self, *args, **kwargs):
        return super(Bot, self).send_voice(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_video_note(self, *args, **kwargs):
        return super(Bot, self).send_video_note(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_location(self, *args, **kwargs):
        return super(Bot, self).send_location(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_venue(self, *args, **kwargs):
        return super(Bot, self).send_venue(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def send_sticker(self, *args, **kwargs):
        return super(Bot, self).send_sticker(*args, **kwargs)

    @chat_locking
    @messagequeue.queuedmessage
    def forward_message(self, *args, **kwargs):
        with self._global_lock:
            if self.forwarding_next_time is not None:
                allow_forwarding = datetime.datetime.utcnow() > self.forwarding_next_time
                if allow_forwarding:
                    self.forwarding_next_time = None
            else:
                allow_forwarding = True

        if not allow_forwarding:
            return None

        try:
            logging.info(f"Native forward_message implementation called (chat_id={kwargs['chat_id']},"
                         f"from_chat_id={kwargs['from_chat_id']}, message_id={kwargs['message_id']})")
            return super(Bot, self).forward_message(*args, **kwargs)
        except err.RetryAfter as e:
            logging.warning(f"telegram.error.RetryAfter handled. Retry in {e.retry_after} seconds")
            with self._global_lock:
                self.forwarding_next_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=e.retry_after + 1.5)
            return None
