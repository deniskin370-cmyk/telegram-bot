import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ID создателя бота — он получает права администратора автоматически
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))

# Telegram ID пользователя @Neworsi — подарки отправляются на этот аккаунт
NEWORSI_USER_ID = int(os.getenv("NEWORSI_USER_ID", "0"))

# DATABASE_URL задаётся на хостинге (Neon / Railway)
# Пример: postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require

# ── Pyrogram userbot ──────────────────────────────────────────────────────────
# Получить на my.telegram.org → «API development tools»
USERBOT_API_ID: int | None = int(os.getenv("USERBOT_API_ID", "0")) or None
USERBOT_API_HASH: str | None = os.getenv("USERBOT_API_HASH") or None
# Сгенерировать один раз: python generate_session.py
USERBOT_SESSION: str | None = os.getenv("USERBOT_SESSION") or None
