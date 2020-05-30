import logging

import telegram


class BotLogsHandler(logging.Handler):
    def __init__(
        self, level=logging.NOTSET, telegram_token=None, proxy_url=None, chat_id=None
    ):
        self.bot = setup_telegram_bot(telegram_token, proxy_url)
        self.chat_id = chat_id
        super(BotLogsHandler, self).__init__(level=level)

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.send_message(chat_id=self.chat_id, text=log_entry)


def setup_telegram_bot(telegram_token, proxy_url=None):
    if proxy_url is not None:
        proxy_settings = telegram.utils.request.Request(proxy_url=proxy_url)
        bot = telegram.Bot(token=telegram_token, request=proxy_settings)
    else:
        bot = telegram.Bot(token=telegram_token)
    return bot
