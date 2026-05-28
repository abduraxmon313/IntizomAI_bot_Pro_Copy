"""
Backwards-compatible thin wrapper that delegates to the new
gamification engine. Kept so older imports keep working.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date

from bot.models.score_log import ScoreLog
from bot.models.plan import Plan
from bot.models.user import User
from bot.services.gamification_service import reward_completion, CompletionReward


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
    result = await session.execute(
        select(func.sum(ScoreLog.score_change)).where(
            and_(
                ScoreLog.user_id == user.id,
                func.date(ScoreLog.created_at) == date.today(),
            )
        )
    )
    return result.scalar() or 0
