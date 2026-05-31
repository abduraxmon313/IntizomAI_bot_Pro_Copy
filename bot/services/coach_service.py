"""
Emotional AI coach — rotating, mood-aware messages.

Tone: supportive, grounded, identity-affirming.
Never toxic. Never shaming. Always points forward.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import TIMEZONE
from bot.models.checkin import DailyCheckin
from bot.models.plan import Plan, PlanStatus
from bot.models.user import User


# ── Templates ────────────────────────────────────────────────
MORNING = [
    "🌅 Yangi kun — yangi imkoniyat. Bugun qaysi cho'qqini zabt etamiz?",
    "☀️ Erta turdingmi? Bu allaqachon kichik g'alaba.",
    "🔥 Bugungi sen — kechagi sendan bir qadam oldinda.",
    "🌱 Har kichik qadam — katta o'zgarishning bir bo'lagi.",
    "💎 Intizom — bu kayfiyat emas, bu qaror.",
    "🚀 Bugun atigi 1% yaxshiroq bo'l — yil oxirida bu 37 baravar.",
    "🧭 Maqsading aniq bo'lsa, yo'l o'zi ko'rinadi. Boshladikmi?",
    "⚡️ Energiya — harakatdan tug'iladi. Birinchi qadamni tashla.",
]

STREAK_WARNING = [
    "🔥 Streakingni qo'ldan chiqarma — {streak} kunlik mehnating xavf ostida.",
    "⚠️ Bugun bittasini ham bajarmasang, {streak} kunlik olov o'chadi.",
    "💪 Yana atigi 1 ta — va kun saqlanadi. Kelajakdagi sen minnatdor bo'ladi.",
    "🛡 Streak — bu sen o'zingga bergan va'da. Uni buzma.",
    "⏳ Kun tugayapti, lekin hali kech emas. Bitta yutuq — va olov yonadi.",
]

LEVEL_UP = [
    "⚡️ Yangi daraja — yangi sen.",
    "🎉 Daraja oshdi! Endi keyingi cho'qqi ko'rinib turibdi.",
    "🏆 Bu shunchaki raqam emas — bu sening o'sganing isboti.",
    "🌟 Yuqoriga! Har daraja — qat'iyatingning mevasi.",
]

PERFECT_DAY = [
    "✨ Mukammal kun! Hech narsa o'tkazib yuborilmadi.",
    "🌟 Bugun sen 1% emas — 100% bo'lding.",
    "💎 Bu kun tarixingda oltin harflar bilan qoladi.",
    "👑 To'liq nazorat. Bugun sen o'z hayotingning xo'jasisan.",
]

COMEBACK = [
    "🔄 Qaytib kelding — bu eng muhim qadam edi.",
    "💪 Tushish — mag'lubiyat emas. To'xtab qolish — mag'lubiyat.",
    "🌱 Yana boshlash — eng kuchli odatlardan biri.",
    "🌅 Har kun — yangi sahifa. Bugun toza varaqdan boshla.",
]

LOW_DISCIPLINE = [
    "🎯 Discipline biroz pasaydi. Bitta kichik yutuq — va u tiklanadi.",
    "📈 Hammasi sening qo'lingda. Bugun bitta narsani uddalab ko'r.",
    "🪄 Katta o'zgarish kichik qadamdan boshlanadi. Bittasini tanla.",
]

HIGH_DISCIPLINE = [
    "🏆 Discipline cho'qqida! Sen o'z shaxsingni qurmoqdasan.",
    "💎 Sen endi shunchaki 'qilaman' deydigon emas — qiluvchisan.",
    "👑 Bu daraja — kamchilikning emas, izchillikning mevasi.",
]

EVENING = [
    "🌙 Kun yakuni. Bugun qaysi qadaming bilan faxrlanasan?",
    "✨ Esda tut: bugungi tanlovlaring — ertangi poydevoring.",
    "🌌 Tinch dam ol. Ertaga yana yangi savash bor.",
    "📖 Bugungi kuningni bir jumlada yakunla — nimadan minnatdorsan?",
]

EMPTY_DAY = [
    "📋 Bugun reja yo'q. Bitta kichik niyatdan boshla.",
    "🌱 Eng kichik reja — eng kuchli boshlanish.",
    "✏️ Bo'sh sahifa — imkoniyat. Bugun nimani uddalashni xohlaysan?",
]


def _pick(pool: list[str], **fmt) -> str:
    return random.choice(pool).format(**fmt)


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────
def message_for_level_up(level: int) -> str:
    return f"{_pick(LEVEL_UP)}\n\n💎 Daraja: <b>{level}</b>"


def message_for_perfect_day() -> str:
    return _pick(PERFECT_DAY)


def message_for_streak_warning(streak: int) -> str:
    return _pick(STREAK_WARNING, streak=streak)


def message_for_comeback() -> str:
    return _pick(COMEBACK)


def message_for_morning() -> str:
    return _pick(MORNING)


def message_for_evening() -> str:
    return _pick(EVENING)


def message_for_empty_day() -> str:
    return _pick(EMPTY_DAY)


# ─────────────────────────────────────────────────────────────
#  Smart contextual coach (used by webapp /api/webapp/coach)
# ─────────────────────────────────────────────────────────────
async def smart_coach_message(session: AsyncSession, user: User) -> dict:
    """
    Returns a contextual, mood-aware message + tone label.
    Decision tree (priority order):
      1. Comeback (≥2 days inactive)
      2. Streak at risk (today not yet completed, has streak)
      3. Low discipline (<35)
      4. High discipline (≥75)
      5. Perfect day standing
      6. Morning vs evening time-of-day
    """
    now = datetime.now(TIMEZONE)
    today = now.date()
    last = user.last_completed_date
    streak = user.streak or 0
    ds = user.discipline_score or 50

    days_idle = (today - last).days if last else 999

    if days_idle >= 2 and streak == 0:
        return {"tone": "comeback", "icon": "🔄", "text": _pick(COMEBACK)}

    if streak >= 2 and last != today:
        return {
            "tone": "warning",
            "icon": "⚠️",
            "text": _pick(STREAK_WARNING, streak=streak),
        }

    if ds < 35:
        return {"tone": "encourage", "icon": "📈", "text": _pick(LOW_DISCIPLINE)}

    # Today has plans but none done?
    today_plans = await session.execute(
        select(Plan).where(
            and_(Plan.user_id == user.id, Plan.plan_date == today)
        )
    )
    today_plans = today_plans.scalars().all()
    today_total = len(today_plans)
    today_done = sum(1 for p in today_plans if p.status == PlanStatus.done)

    if today_total == 0:
        return {"tone": "neutral", "icon": "📋", "text": _pick(EMPTY_DAY)}

    if today_total > 0 and today_done == today_total:
        return {"tone": "celebrate", "icon": "✨", "text": _pick(PERFECT_DAY)}

    if ds >= 75:
        return {"tone": "elite", "icon": "💎", "text": _pick(HIGH_DISCIPLINE)}

    if 5 <= now.hour < 12:
        return {"tone": "morning", "icon": "🌅", "text": _pick(MORNING)}
    if now.hour >= 19:
        return {"tone": "evening", "icon": "🌙", "text": _pick(EVENING)}

    return {"tone": "neutral", "icon": "🌱", "text": _pick(MORNING)}


# ─────────────────────────────────────────────────────────────
#  Daily quest — a single "do this now" focus
# ─────────────────────────────────────────────────────────────
async def daily_quest(session: AsyncSession, user: User) -> dict:
    """Returns a single concrete quest with progress."""
    today = datetime.now(TIMEZONE).date()
    res = await session.execute(
        select(Plan).where(
            and_(Plan.user_id == user.id, Plan.plan_date == today)
        )
    )
    plans = res.scalars().all()
    total = len(plans)
    done = sum(1 for p in plans if p.status == PlanStatus.done)

    if total == 0:
        return {
            "title": "Bugungi 1-rejangni qo'sh",
            "subtitle": "Boshlanish — eng qiyin va eng muhim qadam",
            "progress": 0,
            "target": 1,
            "reward_xp": 5,
            "icon": "✏️",
            "completed": False,
        }

    if done < total:
        return {
            "title": "Bugungi rejalarni yakunla",
            "subtitle": f"{total - done} ta qoldi — har biri seni kuchaytiradi",
            "progress": done,
            "target": total,
            "reward_xp": 10,
            "icon": "🎯",
            "completed": False,
        }

    # All done — perfect day quest already won
    streak = user.streak or 0
    return {
        "title": f"{streak}-kunlik streak saqlandi",
        "subtitle": "Mukammal kun. Ertaga ham kel.",
        "progress": 1,
        "target": 1,
        "reward_xp": 0,
        "icon": "✨",
        "completed": True,
    }
