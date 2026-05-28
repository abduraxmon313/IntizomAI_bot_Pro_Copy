from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from database.db import AsyncSessionLocal
from bot.services.user_service import get_user_by_telegram_id
from bot.services.goal_service import (
    get_user_goals,
    create_goal,
    update_goal,
    delete_goal,
)

router = APIRouter()


class GoalOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    goal_type: str
    period: str
    completed: bool
    created_at: str


class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    goal_type: str
    period: str


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


@router.get("/goals", response_model=list[GoalOut])
async def get_goals(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    goals = await get_user_goals(session, user)
    return [
        GoalOut(
            id=g.id,
            title=g.title,
            description=g.description,
            goal_type=g.goal_type,
            period=g.period,
            completed=g.completed,
            created_at=g.created_at.isoformat(),
        )
        for g in goals
    ]


@router.post("/goals", response_model=GoalOut)
async def add_goal(
    telegram_id: int,
    body: GoalCreate,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    goal = await create_goal(
        session, user, body.title, body.description, body.goal_type, body.period
    )
    return GoalOut(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        goal_type=goal.goal_type,
        period=goal.period,
        completed=goal.completed,
        created_at=goal.created_at.isoformat(),
    )


@router.put("/goals/{goal_id}", response_model=GoalOut)
async def edit_goal(
    goal_id: int,
    telegram_id: int,
    body: GoalUpdate,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    goal = await update_goal(
        session, goal_id, user.id, body.title, body.description, body.completed
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Maqsad topilmadi")
    return GoalOut(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        goal_type=goal.goal_type,
        period=goal.period,
        completed=goal.completed,
        created_at=goal.created_at.isoformat(),
    )


@router.delete("/goals/{goal_id}")
async def remove_goal(
    goal_id: int,
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    ok = await delete_goal(session, goal_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Maqsad topilmadi")
    return {"ok": True}
