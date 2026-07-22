import logging
import asyncio

from aiogram import Router, Bot
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message
from aiogram.exceptions import TelegramBadRequest

from database import is_muted
from config import CREATOR_ID
from userbot import userbot_delete_messages

logger = logging.getLogger(__name__)
router = Router()

# chat_id -> list[message_id] — хранит ID входящих business-сообщений для .del
message_store: dict[int, list[int]] = {}


@router.business_connection()
async def on_business_connection(event: BusinessConnection):
    if event.is_enabled:
        logger.info("Business connection established: user_id=%s, id=%s", event.user.id, event.id)
    else:
        logger.info("Business connection removed: user_id=%s, id=%s", event.user.id, event.id)


async def delete_business_msg(
    bot: Bot,
    business_connection_id: str,
    chat_id: int,
    message_id: int,
) -> bool:
    """Удаляет одно business-сообщение. Возвращает True если успешно."""
    if not business_connection_id:
        logger.warning("business_connection_id is None — удаление невозможно")
        return False

    try:
        await bot.delete_business_messages(
            business_connection_id=business_connection_id,
            chat_id=chat_id,
            message_ids=[message_id],
        )
        logger.info("Удалено сообщение %s в чате %s", message_id, chat_id)
        return True
    except TelegramBadRequest as e:
        logger.warning("Не удалось удалить сообщение %s: %s", message_id, e)
        return False
    except Exception as e:
        logger.error("Ошибка при удалении сообщения %s: %s", message_id, e)
        return False


async def delete_business_messages_bulk(
    bot: Bot,
    business_connection_id: str,
    chat_id: int,
    message_ids: list[int],
) -> int:
    """Удаляет список сообщений. Возвращает количество успешно удалённых."""
    if not message_ids or not business_connection_id:
        return 0
    # Telegram принимает до 100 ID за раз
    deleted = 0
    for i in range(0, len(message_ids), 100):
        chunk = message_ids[i:i + 100]
        try:
            await bot.delete_business_messages(
                business_connection_id=business_connection_id,
                chat_id=chat_id,
                message_ids=chunk,
            )
            deleted += len(chunk)
        except TelegramBadRequest as e:
            logger.warning("Bulk delete error: %s", e)
        except Exception as e:
            logger.error("Bulk delete unexpected error: %s", e)
    return deleted


async def _send_mute_autoreply(bot: Bot, business_connection_id: str, chat_id: int) -> bool:
    """
    Fallback для режима «Автоматизация чатов»: если удалить сообщение нельзя,
    отправляем авто-ответ от имени бизнес-аккаунта.
    Возвращает True если отправка прошла успешно.
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🔇 Ваше сообщение не может быть обработано.",
            business_connection_id=business_connection_id,
        )
        logger.info("Авто-ответ (мут) отправлен в чат %s", chat_id)
        return True
    except Exception as e:
        logger.warning("Не удалось отправить авто-ответ мутированному пользователю в чате %s: %s", chat_id, e)
        return False


async def _handle_muted(message: Message):
    if not message.from_user:
        return
    sender_id = message.from_user.id
    if sender_id == CREATOR_ID:
        return

    # Сохраняем ID входящего сообщения для .del
    chat_id = message.chat.id
    if chat_id not in message_store:
        message_store[chat_id] = []
    message_store[chat_id].append(message.message_id)
    # Ограничиваем хранилище — не больше 500 ID на чат
    if len(message_store[chat_id]) > 500:
        message_store[chat_id] = message_store[chat_id][-500:]

    if not await is_muted(sender_id):
        return

    # Шаг 1: пробуем удалить через Pyrogram userbot (работает в ЛС без Business Premium)
    deleted = await userbot_delete_messages(chat_id, [message.message_id])

    # Шаг 2: если userbot недоступен — пробуем через Bot API (deleteBusinessMessages)
    # Работает если бот подключён через «Подключённые боты» с разрешением «Удалять сообщения»
    if not deleted:
        deleted = await delete_business_msg(
            message.bot,
            message.business_connection_id,
            message.chat.id,
            message.message_id,
        )

    # Шаг 3: оба метода не сработали — отправляем авто-ответ от имени бизнес-аккаунта
    if not deleted and message.business_connection_id:
        await _send_mute_autoreply(
            message.bot,
            message.business_connection_id,
            message.chat.id,
        )


@router.business_message()
async def on_business_message(message: Message):
    await _handle_muted(message)


@router.edited_business_message()
async def on_edited_business_message(message: Message):
    await _handle_muted(message)


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    logger.info(
        "Business messages deleted: chat_id=%s, count=%s",
        event.chat.id,
        len(event.message_ids),
    )
