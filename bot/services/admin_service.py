from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from bot.models.admin import Admin
from bot.models.user import User
from bot.models.plan import Plan, PlanStatus
from bot.config import ADMIN_ID


def get_user_status(total_score: int, streak: int) -> str:
    """Ball va streakga qarab user statusini qaytaradi"""
    if total_score >= 500 and streak >= 14:
        return "🏆 Ustoz"
    elif total_score >= 300 and streak >= 7:
        return "💎 Intizomli"
    elif total_score >= 150 and streak >= 3:
        return "🔥 Focused"
    elif total_score >= 50:
        return "📈 O'sishda"
    elif total_score > 0:
        return "🌱 Yangi boshlovchi"
    else:
        return "😴 Harakatsiz"


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
    """Userning admin ekanligini tekshiradi"""
    if telegram_id == ADMIN_ID:
        return True
    result = await session.execute(
        select(Admin).where(Admin.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none() is not None


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


async def get_users_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.id)))
    return result.scalar()


async def get_all_admins(session: AsyncSession) -> list[Admin]:
    result = await session.execute(select(Admin).order_by(Admin.added_at.desc()))
    return result.scalars().all()


async def add_admin(session: AsyncSession, telegram_id: int, full_name: str = "Noma'lum") -> Admin | None:
    existing = await session.execute(select(Admin).where(Admin.telegram_id == telegram_id))
    if existing.scalar_one_or_none():
        return None
    admin = Admin(telegram_id=telegram_id, full_name=full_name)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def remove_admin(session: AsyncSession, telegram_id: int) -> bool:
    result = await session.execute(select(Admin).where(Admin.telegram_id == telegram_id))
    admin = result.scalar_one_or_none()
    if not admin:
        return False
    await session.delete(admin)
    await session.commit()
    return True


async def get_user_plan_stats(session: AsyncSession, user: User) -> dict:
    """User haqida to'liq statistika"""
    result = await session.execute(
        select(Plan).where(Plan.user_id == user.id)
    )
    plans = result.scalars().all()

    return {
        "total_plans": len(plans),
        "done": len([p for p in plans if p.status == PlanStatus.done]),
        "failed": len([p for p in plans if p.status == PlanStatus.failed]),
        "pending": len([p for p in plans if p.status == PlanStatus.pending]),
    }


async def get_detailed_users_stats(session: AsyncSession) -> dict:
    """Userlar haqida to'liq statistika"""
    users_result = await session.execute(select(User))
    users = users_result.scalars().all()

    total = len(users)

    # Active userlar — kamida 1 ta rejasi borlar
    active_ids_result = await session.execute(
        select(Plan.user_id).distinct()
    )
    active_ids = set(active_ids_result.scalars().all())
    active = len(active_ids)
    inactive = total - active

    # Statuslarga ko'ra ajratish
    status_counts = {
        "🏆 Ustoz": 0,
        "💎 Intizomli": 0,
        "🔥 Focused": 0,
        "📈 O'sishda": 0,
        "🌱 Yangi boshlovchi": 0,
        "😴 Harakatsiz": 0,
    }

    for user in users:
        status = get_user_status(user.total_score, user.streak)
        if status in status_counts:
            status_counts[status] += 1

    # Top 3 user (ball bo'yicha)
    top_users = sorted(users, key=lambda u: u.total_score, reverse=True)[:3]

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "status_counts": status_counts,
        "top_users": top_users,
    }