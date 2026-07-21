import logging
from aiogram import Router
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message

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


@router.edited_business_message()
async def on_edited_business_message(message: Message):
    """Handles edited messages sent via business connection."""
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
