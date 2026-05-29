import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from bot.config import DATABASE_URL


logger = logging.getLogger(__name__)


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# ─────────────────────────────────────────────────────────────
#  Lightweight idempotent migrations for new gamification columns.
#  Postgres (Railway) — uses ADD COLUMN IF NOT EXISTS.
# ─────────────────────────────────────────────────────────────
USER_NEW_COLUMNS = [
    ("xp", "INTEGER DEFAULT 0"),
    ("level", "INTEGER DEFAULT 1"),
    ("longest_streak", "INTEGER DEFAULT 0"),
    ("last_completed_date", "DATE"),
    ("streak_freezes", "INTEGER DEFAULT 0"),
    ("discipline_score", "INTEGER DEFAULT 50"),
    ("weekly_xp", "INTEGER DEFAULT 0"),
    ("perfect_days", "INTEGER DEFAULT 0"),
    ("is_premium", "BOOLEAN DEFAULT FALSE"),
    ("premium_until", "TIMESTAMP"),
    ("onboarded", "BOOLEAN DEFAULT FALSE"),
    ("rank_title", "VARCHAR(40)"),
    ("avatar_emoji", "VARCHAR(8) DEFAULT '🌱'"),
    ("ai_msgs_date", "DATE"),
    ("ai_msgs_count", "INTEGER DEFAULT 0"),
]


async def _run_migrations(conn):
    for col, ddl in USER_NEW_COLUMNS:
        try:
            await conn.execute(
                text(f'ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {ddl}')
            )
        except Exception as e:
            logger.warning(f"Migration skip {col}: {e}")


async def create_tables():
    async with engine.begin() as conn:
        from bot.models import (  # noqa
            user, plan, score_log, admin, goal, achievement, checkin,
            subscription,
        )
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)
