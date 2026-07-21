import asyncio
import logging
from aiogram import Router, Bot
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message

from database import is_muted
from config import CREATOR_ID

logger = logging.getLogger(__name__)
router = Router()


@router.business_connection()
async def on_business_connection(event: BusinessConnection):
    if event.is_enabled:
        logger.info(
            "Business connection established: user_id=%s, connection_id=%s",
            event.user.id, event.id
        )
    else:
        logger.info(
            "Business connection removed: user_id=%s, connection_id=%s",
            event.user.id, event.id
        )


async def _delete_business_message(bot: Bot, message: Message):
    """Удаляет business-сообщение через 0.1 секунды."""
    await asyncio.sleep(0.1)
    try:
        # Пробуем удалить через delete_messages (поддерживает business_connection_id в новых версиях API)
        await bot.delete_messages(
            chat_id=message.chat.id,
            message_ids=[message.message_id]
        )
    except Exception:
        try:
            # Резервный метод
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.warning(
                "Не удалось удалить сообщение замученного %s: %s",
                message.from_user.id if message.from_user else "?", e
            )


@router.business_message()
async def on_business_message(message: Message):
    """
    Ловит все business-сообщения.
    Если отправитель замучен — удаляет сообщение через 0.1 сек.
    Сообщения самого владельца не трогает.
    """
    if not message.from_user:
        return

    sender_id = message.from_user.id

    # Не удаляем сообщения самого владельца
    if sender_id == CREATOR_ID:
        return

    if await is_muted(sender_id):
        bot: Bot = message.bot
        asyncio.create_task(_delete_business_message(bot, message))


@router.edited_business_message()
async def on_edited_business_message(message: Message):
    """Удаляет отредактированные сообщения от замученных пользователей."""
    if not message.from_user:
        return

    sender_id = message.from_user.id

    if sender_id == CREATOR_ID:
        return

    if await is_muted(sender_id):
        bot: Bot = message.bot
        asyncio.create_task(_delete_business_message(bot, message))


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    logger.info(
        "Business messages deleted: chat_id=%s, count=%s",
        event.chat.id, len(event.message_ids)
    )
