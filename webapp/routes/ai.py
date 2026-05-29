"""
AI Coach suhbat (chat) API.

Foydalanuvchi savol bersa — AI uning BARCHA maqsad va rejalarini, streak/discipline
holatini ko'rib, shundan kelib chiqib javob beradi va u bilan suhbatlashadi.
Suhbatlar saqlanmaydi (ephemeral) — frontend tarixni o'zida yuritadi.
"""
import logging
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import TIMEZONE
from bot.models.checkin import DailyCheckin
from bot.models.plan import PlanStatus
from bot.services.ai_service import chat_with_coach
from bot.services.gamification_service import build_user_snapshot
from bot.services.goal_service import get_user_goals
from bot.services.plan_service import get_today_plans
from bot.services.premium_service import check_and_consume_ai, user_is_premium
from bot.services.user_service import get_user_by_telegram_id
from database.db import AsyncSessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage]


class ChatOut(BaseModel):
    reply: str
    is_premium: bool
    remaining: int = -1
    limit: int = -1


GOAL_TYPE_UZ = {
    "yearly": "Yillik",
    "monthly": "Oylik",
    "weekly": "Haftalik",
    "daily": "Kunlik",
}


async def _build_context(session: AsyncSession, user) -> str:
    """Foydalanuvchining joriy holatini AI uchun matn blokiga jamlaydi."""
    snap = await build_user_snapshot(session, user)
    goals = await get_user_goals(session, user)
    today_plans = await get_today_plans(session, user)

    today = datetime.now(TIMEZONE).date()
    res = await session.execute(
        select(DailyCheckin).where(
            and_(DailyCheckin.user_id == user.id, DailyCheckin.checkin_date == today)
        )
    )
    checkin = res.scalar_one_or_none()

    lines = []
    name = (user.full_name or "").split(" ")[0] or "Do'st"
    lines.append(f"Ism: {name}")
    lines.append(
        f"Daraja: {snap.get('level', 1)} | XP: {snap.get('xp', 0)} | "
        f"Streak: {snap.get('streak', 0)} kun (rekord: {user.longest_streak or 0}) | "
        f"Discipline score: {snap.get('discipline_score', 50)}/100"
    )
    lines.append(
        f"Bugungi rejalar: {snap.get('today_done', 0)}/{snap.get('today_total', 0)} bajarildi"
    )
    lines.append(f"Premium: {'ha' if user_is_premium(user) else 'bepul (premium emas)'}")

    # Bugungi rejalar ro'yxati
    if today_plans:
        plan_lines = []
        for p in today_plans[:15]:
            mark = "✅" if p.status == PlanStatus.done else "⬜️"
            t = f" ({p.scheduled_time})" if p.scheduled_time else ""
            plan_lines.append(f"  {mark} {p.title}{t}")
        lines.append("Bugungi rejalar ro'yxati:\n" + "\n".join(plan_lines))
    else:
        lines.append("Bugungi rejalar ro'yxati: bo'sh")

    # Maqsadlar (tur bo'yicha)
    if goals:
        by_type: dict[str, list] = {}
        for g in goals:
            by_type.setdefault(g.goal_type, []).append(g)
        goal_lines = []
        for gtype in ("yearly", "monthly", "weekly", "daily"):
            items = by_type.get(gtype, [])
            if not items:
                continue
            done = sum(1 for g in items if g.completed)
            titles = ", ".join(g.title for g in items[:6] if not g.completed)
            label = GOAL_TYPE_UZ.get(gtype, gtype)
            line = f"  {label}: {done}/{len(items)} bajarildi"
            if titles:
                line += f" | faol: {titles}"
            goal_lines.append(line)
        if goal_lines:
            lines.append("Maqsadlar:\n" + "\n".join(goal_lines))
    else:
        lines.append("Maqsadlar: hali qo'shilmagan")

    # Bugungi kayfiyat / energiya
    if checkin:
        cl = []
        if checkin.mood:
            cl.append(f"kayfiyat {checkin.mood}")
        if checkin.energy:
            cl.append(f"energiya {checkin.energy}/5")
        if cl:
            lines.append("Bugungi holat: " + ", ".join(cl))

    return "\n".join(lines)


@router.post("/ai/chat", response_model=ChatOut)
async def ai_chat(
    telegram_id: int,
    body: ChatIn,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi. Avval botda /start bosing.")

    if not body.messages:
        raise HTTPException(400, "Bo'sh xabar")

    last = body.messages[-1]
    if last.role != "user" or not last.content.strip():
        raise HTTPException(400, "Oxirgi xabar foydalanuvchidan bo'lishi kerak")

    # Kunlik AI limiti (free) — premiumda cheksiz
    limit = await check_and_consume_ai(session, user)
    if not limit.allowed:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Bugungi bepul AI suhbat limiti tugadi ({limit.limit}/kun). "
                "Cheksiz AI Coach uchun Premium oling 💎"
            ),
        )

    # Kontekst qurish xato bersa ham suhbat to'xtamasligi kerak
    try:
        context_block = await _build_context(session, user)
    except Exception as e:
        logger.error(f"⚠️ AI kontekst qurishda xato: {type(e).__name__}: {e}", exc_info=True)
        context_block = "Ma'lumot vaqtincha mavjud emas."

    history = [{"role": m.role, "content": m.content} for m in body.messages]
    reply = await chat_with_coach(context_block, history)

    return ChatOut(
        reply=reply,
        is_premium=user_is_premium(user),
        remaining=limit.remaining,
        limit=limit.limit,
    )
