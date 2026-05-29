"""
Gamification + coach + quest API for the WebApp.
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import TIMEZONE
from bot.models.checkin import DailyCheckin
from bot.services.coach_service import daily_quest, smart_coach_message
from bot.services.gamification_service import build_user_snapshot
from bot.services.user_service import get_user_by_telegram_id
from database.db import AsyncSessionLocal

router = APIRouter()


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


# ─────────────────────────────────────────────────────────────
class CheckinIn(BaseModel):
    mood: Optional[str] = None
    energy: Optional[int] = None


class CheckinOut(BaseModel):
    checkin_date: str
    mood: Optional[str] = None
    energy: Optional[int] = None


# ─────────────────────────────────────────────────────────────
@router.get("/stats")
async def get_stats(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return await build_user_snapshot(session, user)


@router.get("/coach")
async def get_coach(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return await smart_coach_message(session, user)


@router.get("/quest")
async def get_quest(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return await daily_quest(session, user)


# ─────────────────────────────────────────────────────────────
@router.get("/checkin", response_model=Optional[CheckinOut])
async def get_today_checkin(
    telegram_id: int, session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    today = datetime.now(TIMEZONE).date()
    res = await session.execute(
        select(DailyCheckin).where(
            and_(
                DailyCheckin.user_id == user.id,
                DailyCheckin.checkin_date == today,
            )
        )
    )
    row = res.scalar_one_or_none()
    if not row:
        return None
    return CheckinOut(
        checkin_date=str(row.checkin_date),
        mood=row.mood, energy=row.energy,
    )


@router.post("/checkin", response_model=CheckinOut)
async def save_checkin(
    telegram_id: int,
    body: CheckinIn,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    today = datetime.now(TIMEZONE).date()

    res = await session.execute(
        select(DailyCheckin).where(
            and_(
                DailyCheckin.user_id == user.id,
                DailyCheckin.checkin_date == today,
            )
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = DailyCheckin(user_id=user.id, checkin_date=today)
        session.add(row)

    if body.mood is not None:
        row.mood = body.mood
    if body.energy is not None:
        row.energy = body.energy

    await session.commit()
    await session.refresh(row)

    return CheckinOut(
        checkin_date=str(row.checkin_date),
        mood=row.mood, energy=row.energy,
    )
