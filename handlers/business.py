import logging
import asyncio

from aiogram import Router, Bot
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message
from aiogram.exceptions import TelegramBadRequest

from database import is_muted
from config import CREATOR_ID

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
):
    """Удаляет одно business-сообщение через aiogram native method."""
    if not business_connection_id:
        logger.error("business_connection_id is None — удаление невозможно")
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
        err = str(e)
        logger.warning("Не удалось удалить сообщение %s: %s", message_id, err)
        # Уведомляем создателя бота только о неожиданных ошибках
        if "not found" not in err.lower() and CREATOR_ID:
            try:
                await bot.send_message(
                    CREATOR_ID,
                    f"⚠️ <b>Мут: ошибка удаления</b>\n"
                    f"<code>{err}</code>\n\n"
                    f"chat_id: <code>{chat_id}</code> | msg_id: <code>{message_id}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
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

    if await is_muted(sender_id):
        await delete_business_msg(
            message.bot,
            message.business_connection_id,
            message.chat.id,
            message.message_id,
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
