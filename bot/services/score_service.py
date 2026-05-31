"""
Backwards-compatible thin wrapper that delegates to the new
gamification engine. Kept so older imports keep working.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta

import pytz

from bot.config import TIMEZONE
from bot.models.score_log import ScoreLog
from bot.models.plan import Plan
from bot.models.user import User
from bot.services.gamification_service import reward_completion, CompletionReward


def tashkent_day_utc_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    """
    Joriy Tashkent kunining [boshi, oxiri) chegarasini UTC-naive sifatida qaytaradi.

    ScoreLog.created_at UTC-naive (datetime.utcnow) saqlanadi. Foydalanuvchi esa
    Toshkent vaqtida yashaydi. Shu sabab "bugungi ball" ni to'g'ri hisoblash uchun
    Tashkent kunining boshlanish/tugash vaqtlarini UTC ga o'girib filtrlaymiz.
    """
    now_tk = datetime.now(TIMEZONE) if now is None else now
    start_tk = now_tk.replace(hour=0, minute=0, second=0, microsecond=0)
    end_tk = start_tk + timedelta(days=1)
    start_utc = start_tk.astimezone(pytz.utc).replace(tzinfo=None)
    end_utc = end_tk.astimezone(pytz.utc).replace(tzinfo=None)
    return start_utc, end_utc


async def process_plan_result(
    session: AsyncSession,
    user: User,
    plan: Plan,
    is_done: bool,
) -> int:
    """Legacy signature: returns score change (int).
    For the full reward payload use reward_completion() directly."""
    reward = await reward_completion(session, user, plan, is_done)
    return reward.score_change


async def process_plan_result_full(
    session: AsyncSession,
    user: User,
    plan: Plan,
    is_done: bool,
) -> CompletionReward:
    """Returns the full CompletionReward payload."""
    return await reward_completion(session, user, plan, is_done)


async def get_today_score(session: AsyncSession, user: User) -> int:
    """Bugungi (Tashkent vaqti bo'yicha) jami ball o'zgarishi."""
    start_utc, end_utc = tashkent_day_utc_range()
    result = await session.execute(
        select(func.coalesce(func.sum(ScoreLog.score_change), 0)).where(
            and_(
                ScoreLog.user_id == user.id,
                ScoreLog.created_at >= start_utc,
                ScoreLog.created_at < end_utc,
            )
        )
    )
    return result.scalar() or 0
