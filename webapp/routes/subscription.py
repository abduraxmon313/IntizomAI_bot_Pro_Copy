"""
WebApp obuna (premium) holati API.

Frontend ushbu endpoint orqali foydalanuvchining premium ekanini tekshiradi.
Premium bo'lmasa — Mini App'da paywall (ogohlantirish) ko'rsatiladi.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import FREE_DAILY_PLAN_LIMIT, SUBSCRIPTION_PLANS
from bot.services.premium_service import get_status, format_price
from bot.services.user_service import get_user_by_telegram_id
from database.db import AsyncSessionLocal

router = APIRouter()


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


class PlanOut(BaseModel):
    key: str
    title: str
    days: int
    price: int
    price_label: str


class SubscriptionOut(BaseModel):
    is_premium: bool
    premium_until: Optional[str] = None
    days_left: int = 0
    plan: Optional[str] = None
    plan_title: Optional[str] = None
    free_daily_plan_limit: int
    plans: list[PlanOut]


def _plans_catalog() -> list[PlanOut]:
    return [
        PlanOut(
            key=key,
            title=p["title"],
            days=p["days"],
            price=p["price"],
            price_label=format_price(p["price"]),
        )
        for key, p in SUBSCRIPTION_PLANS.items()
    ]


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        # Foydalanuvchi hali botda /start bosmagan — premium emas
        return SubscriptionOut(
            is_premium=False,
            days_left=0,
            free_daily_plan_limit=FREE_DAILY_PLAN_LIMIT,
            plans=_plans_catalog(),
        )

    status = await get_status(session, user)
    return SubscriptionOut(
        is_premium=status.is_premium,
        premium_until=status.premium_until.isoformat() if status.premium_until else None,
        days_left=status.days_left,
        plan=status.plan,
        plan_title=status.plan_title,
        free_daily_plan_limit=FREE_DAILY_PLAN_LIMIT,
        plans=_plans_catalog(),
    )
