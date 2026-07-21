import logging
from aiogram import Router, Bot
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message
from aiogram.methods import DeleteMessage

from database import is_muted
from config import CREATOR_ID

logger = logging.getLogger(__name__)
router = Router()


@router.business_connection()
async def on_business_connection(event: BusinessConnection):
    if event.is_enabled:
        logger.info("Business connection established: user_id=%s, id=%s", event.user.id, event.id)
    else:
        logger.info("Business connection removed: user_id=%s, id=%s", event.user.id, event.id)


async def _delete_business_message(
    bot: Bot,
    business_connection_id: str,
    chat_id: int,
    message_id: int,
    sender_id,
):
    if not business_connection_id:
        logger.error("business_connection_id is None — удаление невозможно")
        if CREATOR_ID:
            try:
                await bot.send_message(
                    CREATOR_ID,
                    "⚠️ <b>Мут не работает</b>: business_connection_id отсутствует.\n"
                    "Отключи и снова подключи бота в Telegram Business.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        return

    try:
        # business_connection_id передаётся через extra_data (aiogram 3.13.1)
        await bot(DeleteMessage(
            chat_id=chat_id,
            message_id=message_id,
            extra_data={"business_connection_id": business_connection_id},
        ))
    except Exception as e:
        err = str(e)
        logger.warning("Не удалось удалить сообщение замученного %s: %s", sender_id, err)
        if CREATOR_ID:
            try:
                await bot.send_message(
                    CREATOR_ID,
                    f"⚠️ <b>Мут: ошибка удаления</b>\n<code>{err}</code>\n\n"
                    "Проверь: Telegram → Бизнес → Подключённые боты → "
                    "включи <b>«Удалять сообщения»</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass


async def _handle_muted(message: Message):
    if not message.from_user:
        return
    sender_id = message.from_user.id
    if sender_id == CREATOR_ID:
        return
    if await is_muted(sender_id):
        await _delete_business_message(
            message.bot,
            message.business_connection_id,
            message.chat.id,
            message.message_id,
            sender_id,
        )


@router.business_message()
async def on_business_message(message: Message):
    await _handle_muted(message)


@router.edited_business_message()
async def on_edited_business_message(message: Message):
    await _handle_muted(message)


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    logger.info("Business messages deleted: chat_id=%s, count=%s", event.chat.id, len(event.message_ids))
