"""
Pyrogram userbot — запускается рядом с aiogram-ботом.
Нужен для удаления сообщений в ЛС (Bot API это не умеет).

Переменные окружения (в .env):
  USERBOT_API_ID    — числовой API ID с my.telegram.org
  USERBOT_API_HASH  — строковый API Hash с my.telegram.org
  USERBOT_SESSION   — строка сессии, сгенерированная generate_session.py
"""
import logging

from pyrogram import Client
from pyrogram.errors import (
    MessageDeleteForbidden,
    MessageIdInvalid,
    FloodWait,
    RPCError,
)

from config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION

logger = logging.getLogger(__name__)

# Глобальный клиент; создаётся при старте бота
userbot: Client | None = None


def get_userbot() -> Client | None:
    return userbot


async def start_userbot() -> bool:
    """
    Инициализирует и запускает Pyrogram-клиент.
    Возвращает True если успешно, False если конфигурация отсутствует.
    """
    global userbot

    if not USERBOT_API_ID or not USERBOT_API_HASH or not USERBOT_SESSION:
        logger.warning(
            "Userbot не настроен: USERBOT_API_ID / USERBOT_API_HASH / USERBOT_SESSION "
            "отсутствуют в .env"
        )
        return False

    try:
        userbot = Client(
            name="miracles_userbot",
            api_id=USERBOT_API_ID,
            api_hash=USERBOT_API_HASH,
            session_string=USERBOT_SESSION,
            in_memory=True,          # не пишет .session-файл, берёт из строки
            no_updates=True,         # слушать апдейты не нужно — только отправка/удаление
        )
        await userbot.start()
        me = await userbot.get_me()
        logger.info("Userbot запущен: @%s (id=%s)", me.username, me.id)
        return True
    except Exception as e:
        logger.error("Не удалось запустить userbot: %s", e)
        userbot = None
        return False


async def stop_userbot() -> None:
    global userbot
    if userbot and userbot.is_connected:
        try:
            await userbot.stop()
            logger.info("Userbot остановлен")
        except Exception as e:
            logger.warning("Ошибка при остановке userbot: %s", e)
    userbot = None


async def userbot_delete_messages(chat_id: int, message_ids: list[int]) -> bool:
    """
    Удаляет сообщения из ЛС через userbot (только входящие, «у всех»).
    Возвращает True если хотя бы одно удаление прошло успешно.
    """
    client = get_userbot()
    if not client or not client.is_connected:
        logger.warning("userbot_delete_messages: клиент недоступен")
        return False

    if not message_ids:
        return False

    success = False
    for msg_id in message_ids:
        try:
            await client.delete_messages(
                chat_id=chat_id,
                message_ids=msg_id,
                revoke=True,   # удалить «у всех», не только у себя
            )
            success = True
            logger.info("Userbot удалил сообщение %s в чате %s", msg_id, chat_id)
        except (MessageDeleteForbidden, MessageIdInvalid):
            logger.debug("Нельзя удалить сообщение %s в чате %s", msg_id, chat_id)
        except FloodWait as e:
            import asyncio
            logger.warning("FloodWait %ss при удалении сообщений", e.value)
            await asyncio.sleep(e.value)
        except RPCError as e:
            logger.warning("RPCError при удалении %s: %s", msg_id, e)
        except Exception as e:
            logger.error("Ошибка userbot_delete_messages: %s", e)

    return success
