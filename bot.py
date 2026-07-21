import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import init_db
from handlers import start, keys, admin, commands, business, buy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "callback_query",
    "inline_query",
    "pre_checkout_query",
    "shipping_query",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
]


async def main():
    await init_db()
    logger.info("Database initialized")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: commands и buy — до business (чтобы .mute/.spam перехватывались первыми)
    dp.include_router(start.router)
    dp.include_router(keys.router)
    dp.include_router(admin.router)
    dp.include_router(commands.router)
    dp.include_router(buy.router)
    dp.include_router(business.router)

    logger.info("Bot starting...")
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)


if __name__ == "__main__":
    asyncio.run(main())
