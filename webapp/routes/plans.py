from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from database.db import AsyncSessionLocal
from bot.services.user_service import get_user_by_telegram_id
from bot.services.plan_service import (
    get_today_plans,
    create_plan_single,
    update_plan_fields,
    delete_plan_by_id,
    get_plans_in_range,
)

router = APIRouter()


class PlanOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    scheduled_time: Optional[str] = None
    plan_date: str
    status: str
    score_value: int
    created_at: str


class UserOut(BaseModel):
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    streak: int
    total_score: int


class PlansResponse(BaseModel):
    user: UserOut
    plans: list[PlanOut]


class PlanCreate(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_time: Optional[str] = None
    plan_date: Optional[str] = None
    score_value: int = 5


class PlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_time: Optional[str] = None
    status: Optional[str] = None


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


def _serialize(p) -> PlanOut:
    return PlanOut(
        id=p.id,
        title=p.title,
        description=p.description,
        scheduled_time=p.scheduled_time,
        plan_date=str(p.plan_date),
        status=p.status.value if hasattr(p.status, "value") else str(p.status),
        score_value=p.score_value,
        created_at=p.created_at.isoformat(),
    )


@router.get("/plans", response_model=PlansResponse)
async def get_user_plans(
    telegram_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    if date_from and date_to:
        plans = await get_plans_in_range(session, user, date_from, date_to)
    else:
        plans = await get_today_plans(session, user)

    return PlansResponse(
        user=UserOut(
            telegram_id=user.telegram_id,
            full_name=user.full_name or "Foydalanuvchi",
            username=user.username,
            streak=user.streak,
            total_score=user.total_score,
        ),
        plans=[_serialize(p) for p in plans],
    )


@router.post("/plans", response_model=PlanOut)
async def add_plan(
    telegram_id: int,
    body: PlanCreate,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    # Free-tier kunlik limit (premium foydalanuvchilarga cheksiz)
    from bot.services.premium_service import check_plan_limit
    limit = await check_plan_limit(session, user, adding=1)
    if not limit.allowed:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Bepul kunlik limit tugadi ({limit.used}/{limit.limit}). "
                "Cheksiz reja uchun Premium oling."
            ),
        )

    plan = await create_plan_single(
        session, user,
        title=body.title,
        description=body.description,
        scheduled_time=body.scheduled_time,
        plan_date_str=body.plan_date,
        score_value=body.score_value or 5,
    )
    return _serialize(plan)


@router.put("/plans/{plan_id}", response_model=PlanOut)
async def edit_plan(
    plan_id: int,
    telegram_id: int,
    body: PlanUpdate,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    # Agar reja "done" yoki "failed" deb belgilansa — gamification dvigatelini
    # ishga tushiramiz (XP, streak, discipline score, achievements yangilanadi).
    # Bu Mini App'dagi belgilash ham botdagidek hisoblanishini ta'minlaydi.
    if body.status in ("done", "failed"):
        from bot.models.plan import Plan, PlanStatus
        from sqlalchemy import and_, select
        from bot.services.gamification_service import reward_completion

        res = await session.execute(
            select(Plan).where(and_(Plan.id == plan_id, Plan.user_id == user.id))
        )
        plan = res.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Reja topilmadi")

        # reward_completion faqat pending rejalarni mukofotlaydi (idempotent).
        if plan.status == PlanStatus.pending:
            await reward_completion(session, user, plan, is_done=(body.status == "done"))
        else:
            # Allaqachon belgilangan — faqat boshqa maydonlar bo'lsa yangilaymiz
            if body.title is not None or body.description is not None or body.scheduled_time is not None:
                await update_plan_fields(
                    session, plan_id, user.id,
                    title=body.title, description=body.description,
                    scheduled_time=body.scheduled_time, status=None,
                )
        await session.refresh(plan)
        return _serialize(plan)

    plan = await update_plan_fields(
        session, plan_id, user.id,
        title=body.title,
        description=body.description,
        scheduled_time=body.scheduled_time,
        status=body.status,
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Reja topilmadi")
    return _serialize(plan)


@router.delete("/plans/{plan_id}")
async def remove_plan(
    plan_id: int,
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    ok = await delete_plan_by_id(session, plan_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Reja topilmadi")
    return {"ok": True}
