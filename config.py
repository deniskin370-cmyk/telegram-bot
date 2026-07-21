import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ID создателя бота — он получает права администратора автоматически
CREATOR_ID = int(os.getenv("CREATOR_ID", "0"))

DB_PATH = "bot.db"
