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


async def _delete_business_message(
    bot: Bot,
    business_connection_id: str,
    chat_id: int,
    message_id: int,
    sender_id,
):
    """Удаляет business-сообщение через 0.1 секунды."""
    await asyncio.sleep(0.1)
    try:
        await bot.delete_messages(
            business_connection_id=business_connection_id,
            chat_id=chat_id,
            message_ids=[message_id],
        )
    except Exception:
        try:
            await bot.delete_message(
                business_connection_id=business_connection_id,
                chat_id=chat_id,
                message_id=message_id,
            )
        except Exception as e:
            logger.warning(
                "Не удалось удалить сообщение замученного %s: %s",
                sender_id, e
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

    if sender_id == CREATOR_ID:
        return

    if await is_muted(sender_id):
        asyncio.create_task(_delete_business_message(
            message.bot,
            message.business_connection_id,
            message.chat.id,
            message.message_id,
            sender_id,
        ))


@router.edited_business_message()
async def on_edited_business_message(message: Message):
    """Удаляет отредактированные сообщения от замученных пользователей."""
    if not message.from_user:
        return

    sender_id = message.from_user.id

    if sender_id == CREATOR_ID:
        return

    if await is_muted(sender_id):
        asyncio.create_task(_delete_business_message(
            message.bot,
            message.business_connection_id,
            message.chat.id,
            message.message_id,
            sender_id,
        ))


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    logger.info(
        "Business messages deleted: chat_id=%s, count=%s",
        event.chat.id, len(event.message_ids)
    )
