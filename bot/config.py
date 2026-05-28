from dotenv import load_dotenv
import os
import pytz

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "productivity_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# O'zbekiston vaqti
TIMEZONE = pytz.timezone("Asia/Tashkent")

# Ball tizimi
SCORE_DONE = 5
SCORE_FAILED = -3
STREAK_BONUS = 2

# Kunlik summary vaqti (Tashkent vaqti)
SUMMARY_HOUR = 23
SUMMARY_MINUTE = 59

# Pending check vaqti (Tashkent vaqti)
PENDING_CHECK_HOUR = 23
PENDING_CHECK_MINUTE = 0