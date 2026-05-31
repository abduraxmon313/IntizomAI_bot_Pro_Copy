"""
Gamification engine — XP, levels, streaks, discipline score, achievements.

This module is the single source of truth for everything that
makes IntizomAI psychologically sticky:

  • XP curve (sub-quadratic — early wins feel fast, mastery feels earned)
  • Streak update with grace day & freeze tokens
  • Discipline Score (0-100) — emotional "identity" metric
  • Achievement unlock check
  • Rank titles
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import TIMEZONE
from bot.models.achievement import Achievement
from bot.models.plan import Plan, PlanStatus
from bot.models.score_log import ScoreLog
from bot.models.user import User


# ─────────────────────────────────────────────────────────────
#  XP CURVE
# ─────────────────────────────────────────────────────────────
def xp_for_level(level: int) -> int:
    """Total XP required to reach `level` from 1.
    Curve: level 2 = 100, lvl 5 ≈ 700, lvl 10 ≈ 2700, lvl 20 ≈ 10800."""
    if level <= 1:
        return 0
    return int(50 * (level - 1) * level)


def level_for_xp(xp: int) -> int:
    lvl = 1
    while xp >= xp_for_level(lvl + 1):
        lvl += 1
        if lvl > 200:
            break
    return lvl


def xp_progress(xp: int) -> tuple[int, int, int, int]:
    """Returns (level, xp_in_level, xp_needed_for_next, percent_0_100)."""
    lvl = level_for_xp(xp)
    base = xp_for_level(lvl)
    nxt = xp_for_level(lvl + 1)
    in_lvl = xp - base
    needed = max(1, nxt - base)
    pct = max(0, min(100, int(in_lvl * 100 / needed)))
    return lvl, in_lvl, needed, pct


# ─────────────────────────────────────────────────────────────
#  RANK TITLES — identity attachment
# ─────────────────────────────────────────────────────────────
RANKS = [
    (1,  "🌱 Boshlovchi",   "🌱"),
    (3,  "🔰 O'rganuvchi",  "🔰"),
    (5,  "⚡ Faol",          "⚡"),
    (8,  "🔥 Disciplined",   "🔥"),
    (12, "💎 Intizomli",     "💎"),
    (18, "🏆 Ustoz",         "🏆"),
    (25, "👑 Legend",        "👑"),
    (35, "🌌 Mythic",        "🌌"),
]


def rank_for_level(level: int) -> tuple[str, str]:
    title, emoji = RANKS[0][1], RANKS[0][2]
    for lvl_min, t, e in RANKS:
        if level >= lvl_min:
            title, emoji = t, e
    return title, emoji


# ─────────────────────────────────────────────────────────────
#  ACHIEVEMENTS catalogue
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AchDef:
    code: str
    title: str
    icon: str
    rarity: str = "common"  # common | rare | epic | legendary


ACHIEVEMENTS: list[AchDef] = [
    AchDef("first_step",   "Birinchi qadam",  "🌱", "common"),
    AchDef("streak_3",     "Olov yondi",      "🔥", "common"),
    AchDef("streak_7",     "Bir hafta",       "⚡", "rare"),
    AchDef("streak_14",    "Ikki hafta",      "💪", "rare"),
    AchDef("streak_30",    "Bir oy",          "💎", "epic"),
    AchDef("streak_100",   "Yuz kun",         "🌌", "legendary"),
    AchDef("level_5",      "5-daraja",        "⭐", "common"),
    AchDef("level_10",     "10-daraja",       "🌟", "rare"),
    AchDef("level_25",     "25-daraja",       "👑", "epic"),
    AchDef("perfect_day",  "Mukammal kun",    "✨", "rare"),
    AchDef("early_bird",   "Erta qush",       "🌅", "common"),
    AchDef("night_owl",    "Tungi ishchi",    "🌙", "common"),
    AchDef("100_done",     "100 ta bajarildi","🎯", "rare"),
    AchDef("500_done",     "500 ta bajarildi","🏆", "epic"),
    AchDef("comeback",     "Qaytdim",         "🔄", "rare"),
]
ACH_INDEX = {a.code: a for a in ACHIEVEMENTS}


# ─────────────────────────────────────────────────────────────
#  Result type
# ─────────────────────────────────────────────────────────────
@dataclass
class CompletionReward:
    xp_gained: int = 0
    score_change: int = 0
    leveled_up: bool = False
    new_level: int = 1
    streak_extended: bool = False
    new_streak: int = 0
    new_unlocks: list[Achievement] = field(default_factory=list)
    discipline_score: int = 50
    perfect_day: bool = False


# ─────────────────────────────────────────────────────────────
#  STREAK
# ─────────────────────────────────────────────────────────────
def _today() -> date:
    return datetime.now(TIMEZONE).date()


def _update_streak_on_complete(user: User) -> bool:
    """Returns True when the streak was extended (i.e. first complete today)."""
    today = _today()
    last = user.last_completed_date

    if last == today:
        return False  # already counted today

    if last is None:
        user.streak = 1
    elif last == today - timedelta(days=1):
        user.streak += 1
    elif last == today - timedelta(days=2) and user.streak_freezes > 0:
        # auto-burn one freeze for a single missed day
        user.streak_freezes -= 1
        user.streak += 1
    else:
        user.streak = 1

    user.last_completed_date = today
    if user.streak > (user.longest_streak or 0):
        user.longest_streak = user.streak
    return True


# ─────────────────────────────────────────────────────────────
#  DISCIPLINE SCORE 0..100
# ─────────────────────────────────────────────────────────────
async def _recompute_discipline_score(session: AsyncSession, user: User) -> int:
    """
    Discipline score = weighted blend of:
      • 30-day completion rate (50%)
      • current streak vs 30 cap (25%)
      • 7-day activity intensity (15%)
      • inactivity penalty (10%)
    """
    today = _today()
    window_start = today - timedelta(days=29)

    res = await session.execute(
        select(Plan).where(
            and_(
                Plan.user_id == user.id,
                Plan.plan_date >= window_start,
                Plan.plan_date <= today,
            )
        )
    )
    plans = res.scalars().all()

    total = len(plans)
    done = sum(1 for p in plans if p.status == PlanStatus.done)
    completion_rate = (done / total) if total else 0.0

    streak_norm = min(1.0, (user.streak or 0) / 30.0)

    last7 = today - timedelta(days=6)
    last7_done = sum(
        1 for p in plans if p.plan_date >= last7 and p.status == PlanStatus.done
    )
    intensity = min(1.0, last7_done / 14.0)  # 2/day saturates

    # Inactivity penalty
    if user.last_completed_date is None:
        inactivity = 0.0
    else:
        days_idle = (today - user.last_completed_date).days
        inactivity = max(0.0, 1.0 - (days_idle / 7.0))

    score = (
        completion_rate * 50
        + streak_norm * 25
        + intensity * 15
        + inactivity * 10
    )
    score_int = int(round(max(0, min(100, score))))
    user.discipline_score = score_int
    return score_int


# ─────────────────────────────────────────────────────────────
#  ACHIEVEMENTS unlock detection
# ─────────────────────────────────────────────────────────────
async def _user_unlocked_codes(session: AsyncSession, user: User) -> set[str]:
    res = await session.execute(
        select(Achievement.code).where(Achievement.user_id == user.id)
    )
    return set(res.scalars().all())


async def _check_unlocks(session: AsyncSession, user: User) -> list[Achievement]:
    today = _today()
    unlocked = await _user_unlocked_codes(session, user)
    new: list[AchDef] = []

    if user.streak >= 1 and "first_step" not in unlocked:
        new.append(ACH_INDEX["first_step"])
    if user.streak >= 3 and "streak_3" not in unlocked:
        new.append(ACH_INDEX["streak_3"])
    if user.streak >= 7 and "streak_7" not in unlocked:
        new.append(ACH_INDEX["streak_7"])
    if user.streak >= 14 and "streak_14" not in unlocked:
        new.append(ACH_INDEX["streak_14"])
    if user.streak >= 30 and "streak_30" not in unlocked:
        new.append(ACH_INDEX["streak_30"])
    if user.streak >= 100 and "streak_100" not in unlocked:
        new.append(ACH_INDEX["streak_100"])

    if user.level >= 5 and "level_5" not in unlocked:
        new.append(ACH_INDEX["level_5"])
    if user.level >= 10 and "level_10" not in unlocked:
        new.append(ACH_INDEX["level_10"])
    if user.level >= 25 and "level_25" not in unlocked:
        new.append(ACH_INDEX["level_25"])

    # Total done plans
    done_total = await session.scalar(
        select(func.count(Plan.id)).where(
            and_(Plan.user_id == user.id, Plan.status == PlanStatus.done)
        )
    ) or 0
    if done_total >= 100 and "100_done" not in unlocked:
        new.append(ACH_INDEX["100_done"])
    if done_total >= 500 and "500_done" not in unlocked:
        new.append(ACH_INDEX["500_done"])

    # Time-of-day cosmetic
    hour = datetime.now(TIMEZONE).hour
    if hour < 7 and "early_bird" not in unlocked:
        new.append(ACH_INDEX["early_bird"])
    if hour >= 22 and "night_owl" not in unlocked:
        new.append(ACH_INDEX["night_owl"])

    rows: list[Achievement] = []
    for d in new:
        row = Achievement(
            user_id=user.id,
            code=d.code, title=d.title, icon=d.icon, rarity=d.rarity,
        )
        session.add(row)
        rows.append(row)
    return rows


# ─────────────────────────────────────────────────────────────
#  PUBLIC: process plan completion
# ─────────────────────────────────────────────────────────────
async def reward_completion(
    session: AsyncSession,
    user: User,
    plan: Plan,
    is_done: bool,
) -> CompletionReward:
    """
    Atomic reward step. Updates user stats, writes ScoreLog, persists
    achievements. Caller is responsible for commit boundaries — we use
    flush + commit at the end so the whole reward is consistent.
    """
    out = CompletionReward()
    out.new_level = user.level or 1
    out.new_streak = user.streak or 0

    if plan.status != PlanStatus.pending:
        return out  # idempotent — never reward twice

    if is_done:
        # XP = base score_value × streak multiplier (capped)
        base = max(1, plan.score_value or 5)
        streak_mult = 1.0 + min(0.5, (user.streak or 0) * 0.02)  # +2% per day, max +50%
        xp_gained = int(round(base * streak_mult))

        user.xp = (user.xp or 0) + xp_gained
        user.weekly_xp = (user.weekly_xp or 0) + xp_gained
        user.total_score = (user.total_score or 0) + base

        prev_level = user.level or 1
        new_level = level_for_xp(user.xp)
        user.level = new_level

        out.xp_gained = xp_gained
        out.score_change = base
        out.leveled_up = new_level > prev_level
        out.new_level = new_level

        out.streak_extended = _update_streak_on_complete(user)
        out.new_streak = user.streak

        # Rank refresh
        title, emoji = rank_for_level(user.level)
        user.rank_title = title
        user.avatar_emoji = emoji

        plan.status = PlanStatus.done

        log = ScoreLog(
            user_id=user.id,
            plan_id=plan.id,
            score_change=base,
            reason=f"✅ '{plan.title}' bajarildi (+{xp_gained} XP)",
        )
        session.add(log)
    else:
        score_change = -3
        user.total_score = (user.total_score or 0) + score_change
        out.score_change = score_change
        plan.status = PlanStatus.failed

        log = ScoreLog(
            user_id=user.id,
            plan_id=plan.id,
            score_change=score_change,
            reason=f"❌ '{plan.title}' bajarilmadi",
        )
        session.add(log)

    user.last_active = datetime.utcnow()

    # Perfect-day detection (all today's plans done after this one)
    # Himoyalangan: bu yerda xato bo'lsa ham asosiy belgilash buzilmasligi kerak.
    try:
        today = _today()
        pending_today = await session.scalar(
            select(func.count(Plan.id)).where(
                and_(
                    Plan.user_id == user.id,
                    Plan.plan_date == today,
                    Plan.status == PlanStatus.pending,
                    Plan.id != plan.id,
                )
            )
        ) or 0
        total_today = await session.scalar(
            select(func.count(Plan.id)).where(
                and_(Plan.user_id == user.id, Plan.plan_date == today)
            )
        ) or 0
        if is_done and total_today >= 2 and pending_today == 0:
            out.perfect_day = True
            user.perfect_days = (user.perfect_days or 0) + 1
            # Bonus XP for perfect day
            bonus = 15
            user.xp += bonus
            user.weekly_xp = (user.weekly_xp or 0) + bonus
            out.xp_gained += bonus
            new_level = level_for_xp(user.xp)
            if new_level > user.level:
                out.leveled_up = True
                user.level = new_level
                out.new_level = new_level
            # Unlock perfect_day badge if first time
            existing = await session.scalar(
                select(Achievement).where(
                    and_(Achievement.user_id == user.id, Achievement.code == "perfect_day")
                )
            )
            if not existing:
                row = Achievement(
                    user_id=user.id, code="perfect_day",
                    title="Mukammal kun", icon="✨", rarity="rare",
                )
                session.add(row)
                out.new_unlocks.append(row)
    except Exception:
        pass

    # Discipline score (himoyalangan)
    try:
        await session.flush()
        out.discipline_score = await _recompute_discipline_score(session, user)
    except Exception:
        out.discipline_score = user.discipline_score or 50

    # Achievement unlocks (himoyalangan — xato bo'lsa belgilash buzilmaydi)
    if is_done:
        try:
            more = await _check_unlocks(session, user)
            out.new_unlocks.extend(more)
        except Exception:
            pass

    await session.commit()
    return out


# ─────────────────────────────────────────────────────────────
#  BACKFILL — eski (gamification'dan oldingi) aktivlikni tiklash
# ─────────────────────────────────────────────────────────────
async def _backfill_user_stats(session: AsyncSession, user: User) -> None:
    """
    Agar foydalanuvchining bajarilgan rejalari bo'lsa-yu, lekin XP hali
    hisoblanmagan bo'lsa (0), mavjud bajarilgan rejalardan XP, daraja,
    total_score, streak va discipline score'ni qayta tiklaydi.

    Bu faqat bir marta ishlaydi (XP > 0 bo'lgach qayta hisoblamaydi),
    shuning uchun har bir foydalanuvchining qiymati o'ziga mos bo'ladi.
    """
    if (user.xp or 0) > 0:
        return  # allaqachon hisoblangan — tegmaymiz

    # Barcha bajarilgan rejalar
    res = await session.execute(
        select(Plan).where(
            and_(Plan.user_id == user.id, Plan.status == PlanStatus.done)
        )
    )
    done_plans = res.scalars().all()
    if not done_plans:
        # bajarilgan reja yo'q — faqat discipline'ni yangilab qo'yamiz
        await _recompute_discipline_score(session, user)
        return

    # XP va total_score ni bajarilgan rejalardan tiklaymiz
    total_xp = sum(max(1, p.score_value or 5) for p in done_plans)
    user.xp = total_xp
    user.total_score = max(user.total_score or 0, total_xp)
    user.level = level_for_xp(user.xp)

    title, emoji = rank_for_level(user.level)
    user.rank_title = title
    user.avatar_emoji = emoji

    # Streak'ni bajarilgan kunlardan tiklaymiz
    done_dates = sorted({p.plan_date for p in done_plans if p.plan_date})
    if done_dates:
        user.last_completed_date = done_dates[-1]
        # ketma-ket kunlar bo'yicha eng uzun joriy streak
        today = _today()
        streak = 0
        cursor = done_dates[-1]
        date_set = set(done_dates)
        # faqat oxirgi kun bugun yoki kecha bo'lsa joriy streak hisoblanadi
        if cursor >= today - timedelta(days=1):
            d = cursor
            while d in date_set:
                streak += 1
                d = d - timedelta(days=1)
        user.streak = streak
        user.longest_streak = max(user.longest_streak or 0, streak)

    await session.flush()
    await _recompute_discipline_score(session, user)
    await session.commit()


# ─────────────────────────────────────────────────────────────
#  PUBLIC: snapshot for webapp
# ─────────────────────────────────────────────────────────────
async def build_user_snapshot(session: AsyncSession, user: User) -> dict:
    # Backfill: agar foydalanuvchida bajarilgan rejalar bor-u, lekin XP/discipline
    # hali hisoblanmagan bo'lsa (eski rejalar gamification'dan oldin bajarilgan),
    # ularni mavjud ma'lumotdan tiklaymiz — shunda Asosiy sahifa har bir
    # foydalanuvchi uchun o'ziga mos qiymat ko'rsatadi.
    try:
        await _backfill_user_stats(session, user)
    except Exception:
        pass

    lvl, in_lvl, needed, pct = xp_progress(user.xp or 0)
    title, emoji = rank_for_level(lvl)

    today = _today()
    today_plans = await session.execute(
        select(Plan).where(
            and_(Plan.user_id == user.id, Plan.plan_date == today)
        )
    )
    today_plans = today_plans.scalars().all()
    today_done = sum(1 for p in today_plans if p.status == PlanStatus.done)
    today_total = len(today_plans)

    achs_res = await session.execute(
        select(Achievement)
        .where(Achievement.user_id == user.id)
        .order_by(Achievement.unlocked_at.desc())
    )
    achs = achs_res.scalars().all()

    # Streak status: at_risk if last completed wasn't today
    risk = (
        user.last_completed_date is None
        or user.last_completed_date < today
    )

    return {
        "level": lvl,
        "xp": user.xp or 0,
        "xp_in_level": in_lvl,
        "xp_needed": needed,
        "xp_percent": pct,
        "streak": user.streak or 0,
        "longest_streak": user.longest_streak or 0,
        "streak_at_risk": risk,
        "streak_freezes": user.streak_freezes or 0,
        "discipline_score": user.discipline_score or 50,
        "rank_title": title,
        "rank_emoji": emoji,
        "is_premium": bool(user.premium_until and user.premium_until > datetime.utcnow()),
        "perfect_days": user.perfect_days or 0,
        "today_done": today_done,
        "today_total": today_total,
        "today_completion_pct": (
            int(today_done * 100 / today_total) if today_total else 0
        ),
        "achievements": [
            {
                "code": a.code,
                "title": a.title,
                "icon": a.icon,
                "rarity": a.rarity,
                "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None,
            }
            for a in achs
        ],
    }
