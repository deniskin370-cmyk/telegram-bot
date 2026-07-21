import logging
from aiogram import Router
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message

from database import is_muted

logger = logging.getLogger(__name__)
router = Router()


@router.business_connection()
async def on_business_connection(event: BusinessConnection):
    """Handles business connection / disconnection events."""
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


@router.business_message()
async def on_business_message(message: Message):
    """
    Обрабатывает все входящие business-сообщения.
    Если отправитель замучен — удаляет сообщение мгновенно.
    """
    # Проверяем: это сообщение от собеседника (не от владельца бота)
    # from_user.id совпадает с chat.id в личке
    sender_id = message.from_user.id if message.from_user else None
    if sender_id and await is_muted(sender_id):
        try:
            await message.delete()
        except Exception as e:
            logger.warning("Не удалось удалить сообщение замученного: %s", e)
        return


@router.edited_business_message()
async def on_edited_business_message(message: Message):
    """Handles edited messages sent via business connection."""
    # Если редактирует замученный — удаляем и это
    sender_id = message.from_user.id if message.from_user else None
    if sender_id and await is_muted(sender_id):
        try:
            await message.delete()
        except Exception as e:
            logger.warning("Не удалось удалить отредактированное сообщение замученного: %s", e)
        return

    logger.info(
        "Business message edited: chat_id=%s, message_id=%s",
        message.chat.id, message.message_id
    )


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    """Handles deleted business messages notification."""
    logger.info(
        "Business messages deleted: chat_id=%s, count=%s",
        event.chat.id, len(event.message_ids)
    )
