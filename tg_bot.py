import logging
import os
import random
from functools import partial
from typing import Dict, Optional, Union

import redis
from dotenv import load_dotenv
import telegram
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Filters, ConversationHandler, RegexHandler
from telegram.ext import MessageHandler, CommandHandler
from telegram.ext import Updater

from constants import NEW_QUESTION_TEXT, SCORE_TEXT, SURRENDER_TEXT
from tg_log_handler import BotLogsHandler
from utils import strip_answer, load_quiz_data

logger = logging.getLogger("TelegramQuizBot")
ASKING, ANSWERING = range(2)


def get_user_id_key(user_id: Union[str, int]) -> str:
    return "".join(["tg_", str(user_id)])


def setup_bot(
    token: str, quiz_data: Dict, redis: redis.Redis, proxy_url: str = None
) -> Updater:
    request_kwargs = None
    if proxy_url is not None:
        request_kwargs = {
            "proxy_url": proxy_url,
        }
    updater = Updater(token=token, request_kwargs=request_kwargs)
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_handler),],
        states={
            ASKING: [
                RegexHandler(
                    NEW_QUESTION_TEXT,
                    partial(
                        handle_new_question_request, quiz_data=quiz_data, redis=redis
                    ),
                ),
                RegexHandler(SCORE_TEXT, partial(handle_score_request, redis=redis)),
            ],
            ANSWERING: [
                RegexHandler(
                    SURRENDER_TEXT,
                    partial(handle_surrender_request, quiz_data=quiz_data, redis=redis),
                ),
                RegexHandler(SCORE_TEXT, partial(handle_score_request, redis=redis)),
                MessageHandler(
                    Filters.text,
                    partial(handle_solution_attempt, quiz_data=quiz_data, redis=redis),
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler),],
    )
    updater.dispatcher.add_handler(conversation_handler)
    updater.dispatcher.add_error_handler(error)
    return updater


def start_bot(updater: Updater) -> None:
    updater.start_polling()
    logger.info("Bot started.")
    updater.idle()


def start_handler(bot: telegram.Bot, update: telegram.Update) -> int:
    menu_buttons_layout = [
        [NEW_QUESTION_TEXT, SURRENDER_TEXT],
        [SCORE_TEXT],
    ]
    reply_markup = ReplyKeyboardMarkup(menu_buttons_layout)
    bot.send_message(
        chat_id=update.message.chat_id,
        text="Привет! Я викторинный бот :)",
        reply_markup=reply_markup,
    )
    return ASKING


def cancel_handler(bot: telegram.Bot, update: telegram.Update) -> int:
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} завершил игру.")
    update.message.reply_text(
        "Пока! Заходи, если захочешь еще сыграть.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def error(bot: telegram.Bot, update: telegram.Update, error: telegram.error) -> None:
    logger.warning(f'Update "{update}" caused error "{error}"')


def handle_new_question_request(
    bot: telegram.Bot, update: telegram.Update, quiz_data: Dict, redis: redis.Redis
) -> int:
    user_id = update.message.chat_id
    user_id_key = get_user_id_key(user_id)
    random_question = random.choice(list(quiz_data.keys()))
    redis.set(user_id_key, random_question)
    bot.send_message(chat_id=user_id, text=random_question)
    return ANSWERING


def handle_score_request(
    bot: telegram.Bot, update: telegram.Update, redis: redis.Redis
) -> Optional[int]:
    user_id = update.message.chat_id
    bot.send_message(chat_id=user_id, text="Данная функция временно недоступна.")
    return None  # returning None means state doesn't change


def handle_surrender_request(
    bot: telegram.Bot, update: telegram.Update, quiz_data: Dict, redis: redis.Redis
) -> int:
    user_id = update.message.chat_id
    user_id_key = get_user_id_key(user_id)
    question = redis.get(user_id_key).decode()
    correct_answer = strip_answer(quiz_data[question])
    bot.send_message(chat_id=user_id, text=f"Верный ответ - {correct_answer}")
    return ASKING


def handle_solution_attempt(
    bot: telegram.Bot, update: telegram.Update, quiz_data: Dict, redis: redis.Redis
) -> int:
    message = update.message.text
    user_id = update.message.chat_id
    user_id_key = get_user_id_key(user_id)

    question = redis.get(user_id_key).decode()
    correct_answer = strip_answer(quiz_data[question])
    if message == correct_answer:
        bot.send_message(
            chat_id=user_id,
            text="Правильно! Поздравляю! "
            "Для следующего вопроса нажми «Новый вопрос»",
        )
        return ASKING
    else:
        bot.send_message(chat_id=user_id, text="Неправильно... Попробуешь ещё раз?")
        return ANSWERING


if __name__ == "__main__":
    load_dotenv()
    telegram_quiz_bot_token = os.getenv("TELEGRAM_QUIZ_BOT_TOKEN")
    telegram_log_bot_token = os.getenv("TELEGRAM_LOG_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    proxy_url = os.getenv("TELEGRAM_PROXY_URL", None)
    redis_url, redis_port = os.getenv("REDIS_CONN").rsplit(":")
    redis_password = os.getenv("REDIS_PASSWORD")
    quiz_data_filename = os.getenv("QUIZ_DATA_FILE", 'output.json')

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.setLevel(logging.DEBUG)
    bot_handler = BotLogsHandler(
        level=logging.INFO,
        telegram_token=telegram_log_bot_token,
        proxy_url=proxy_url,
        chat_id=chat_id,
    )
    bot_handler.setFormatter(formatter)
    logger.addHandler(bot_handler)

    try:
        quiz_data = load_quiz_data(quiz_data_filename)
        redis = redis.Redis(
            host=redis_url, port=redis_port, db=0, password=redis_password
        )
        updater = setup_bot(
            token=telegram_quiz_bot_token,
            quiz_data=quiz_data,
            redis=redis,
            proxy_url=proxy_url,
        )
        start_bot(updater)
    except Exception as err:
        logger.error("Unexpected error occurred:")
        logger.error(err, exc_info=True)
