"""
Одноразовый скрипт для генерации USERBOT_SESSION.

Запусти ОДИН РАЗ на своём сервере:
    python generate_session.py

Введи номер телефона и код из SMS / Telegram.
Скопируй полученную строку в .env как USERBOT_SESSION=...

После этого скрипт больше не нужен (можно удалить).
"""
import asyncio
from pyrogram import Client
from config import USERBOT_API_ID, USERBOT_API_HASH


async def main():
    if not USERBOT_API_ID or not USERBOT_API_HASH:
        print("❌ Добавь USERBOT_API_ID и USERBOT_API_HASH в .env и запусти снова.")
        return

    async with Client(
        name="session_gen",
        api_id=USERBOT_API_ID,
        api_hash=USERBOT_API_HASH,
    ) as app:
        session_string = await app.export_session_string()

    print("\n" + "=" * 60)
    print("✅ Строка сессии сгенерирована!")
    print("Добавь в .env:")
    print(f"USERBOT_SESSION={session_string}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
