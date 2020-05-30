import logging
import os
import random
from typing import Dict, Union

import redis as redis
import vk_api
from dotenv import load_dotenv
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

from constants import NEW_QUESTION_TEXT, SCORE_TEXT, SURRENDER_TEXT
from tg_log_handler import BotLogsHandler
from utils import load_quiz_data, strip_answer

logger = logging.getLogger("VKQuizBot")


def get_user_id_key(user_id: Union[str, int]) -> str:
    return "".join(["vk_", str(user_id)])


def is_new_player(event: vk_api.longpoll.VkEventType, redis: redis.Redis) -> bool:
    user_id = event.user_id
    user_id_key = get_user_id_key(user_id)
    record = redis.get(user_id_key)
    if record:
        return False
    return True


def start_bot(token: str, quiz_data: Dict, redis: redis.Redis) -> None:
    vk_session = vk_api.VkApi(token=token)
    long_poll = VkLongPoll(vk_session)

    logger.info("Starting to listen for new messages.")
    vk = vk_session.get_api()
    for event in long_poll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            new_player = is_new_player(event=event, redis=redis)
            if new_player:
                handle_start(event=event, vk=vk, redis=redis)
            if event.text == NEW_QUESTION_TEXT:
                handle_new_question_request(
                    event=event, vk=vk, quiz_data=quiz_data, redis=redis
                )
            elif event.text == SURRENDER_TEXT:
                handle_surrender_request(
                    event=event, vk=vk, quiz_data=quiz_data, redis=redis
                )
            elif event.text == SCORE_TEXT:
                handle_score_request(event=event, vk=vk, redis=redis)
            else:
                handle_solution_attempt(
                    event=event, vk=vk, quiz_data=quiz_data, redis=redis
                )


def get_keyboard() -> Dict:
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button(NEW_QUESTION_TEXT, color=VkKeyboardColor.DEFAULT)
    keyboard.add_button(SURRENDER_TEXT, color=VkKeyboardColor.DEFAULT)
    keyboard.add_line()
    keyboard.add_button(SCORE_TEXT, color=VkKeyboardColor.DEFAULT)
    return keyboard.get_keyboard()


def handle_start(
    event: vk_api.longpoll.VkEventType,
    vk: vk_api.vk_api.VkApiMethod,
    redis: redis.Redis,
) -> None:
    user_id_key = get_user_id_key(event.user_id)
    redis.set(user_id_key, "started_playing")
    vk.messages.send(
        user_id=event.user_id,
        message="Привет! Я викторинный бот, давай сыграем?!",
        random_id=get_random_id(),
        keyboard=get_keyboard(),
    )


def handle_new_question_request(
    event: vk_api.longpoll.VkEventType,
    vk: vk_api.vk_api.VkApiMethod,
    quiz_data: Dict,
    redis: redis.Redis,
) -> None:
    user_id = event.user_id
    user_id_key = get_user_id_key(user_id)
    random_question = random.choice(list(quiz_data.keys()))
    redis.set(user_id_key, random_question)
    vk.messages.send(
        user_id=user_id,
        message=random_question,
        random_id=get_random_id(),
        keyboard=get_keyboard(),
    )


def handle_score_request(
    event: vk_api.longpoll.VkEventType,
    vk: vk_api.vk_api.VkApiMethod,
    redis: redis.Redis,
) -> None:
    user_id = event.user_id
    vk.messages.send(
        user_id=user_id,
        message="Данная функция временно недоступна.",
        random_id=get_random_id(),
        keyboard=get_keyboard(),
    )


def clear_last_user_question(key: str, redis: redis.Redis) -> None:
    redis.set(key, "None")


def handle_surrender_request(
    event: vk_api.longpoll.VkEventType,
    vk: vk_api.vk_api.VkApiMethod,
    quiz_data: Dict,
    redis: redis.Redis,
) -> None:
    user_id = event.user_id
    user_id_key = get_user_id_key(user_id)
    question = redis.get(user_id_key).decode()
    correct_answer = strip_answer(quiz_data[question])
    vk.messages.send(
        user_id=user_id,
        message=f"Верный ответ - {correct_answer}",
        random_id=get_random_id(),
        keyboard=get_keyboard(),
    )
    clear_last_user_question(key=user_id_key, redis=redis)


def handle_solution_attempt(
    event: vk_api.longpoll.VkEventType,
    vk: vk_api.vk_api.VkApiMethod,
    quiz_data: Dict,
    redis: redis.Redis,
) -> None:
    message = event.text
    user_id = event.user_id
    user_id_key = get_user_id_key(user_id)

    question = redis.get(user_id_key).decode()
    correct_answer = strip_answer(quiz_data[question])
    if message == correct_answer:
        vk.messages.send(
            user_id=user_id,
            message="Правильно! Поздравляю! "
            "Для следующего вопроса нажми «Новый вопрос»",
            random_id=get_random_id(),
            keyboard=get_keyboard(),
        )
    else:
        vk.messages.send(
            user_id=user_id,
            message="Неправильно... Попробуешь ещё раз?",
            random_id=get_random_id(),
            keyboard=get_keyboard(),
        )


if __name__ == "__main__":
    load_dotenv()
    vk_token = os.getenv("VK_GROUP_TOKEN")
    telegram_log_bot_token = os.getenv("TELEGRAM_LOG_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    proxy_url = os.getenv("TELEGRAM_PROXY_URL", None)
    redis_url, redis_port = os.getenv("REDIS_CONN").rsplit(":")
    redis_password = os.getenv("REDIS_PASSWORD")
    quiz_data_filename = os.getenv("QUIZ_DATA_FILE")

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
        start_bot(token=vk_token, quiz_data=quiz_data, redis=redis)
    except Exception as err:
        logger.error("Unexpected error occurred:")
        logger.error(err, exc_info=True)
