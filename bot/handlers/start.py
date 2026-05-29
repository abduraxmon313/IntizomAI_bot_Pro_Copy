import os

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.reply_keys import main_reply_keyboard
from bot.services.gamification_service import xp_progress, rank_for_level
from bot.services.user_service import get_or_create_user, get_user_by_telegram_id
from bot.services.premium_service import user_is_premium, days_left

router = Router()


WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()


def _webapp_kb(is_premium: bool) -> InlineKeyboardMarkup | None:
    rows = []
    if WEBAPP_URL:
        rows.append([InlineKeyboardButton(
            text="✨ Mini App ochish",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )])
    if not is_premium:
        rows.append([InlineKeyboardButton(
            text="💎 Obuna sotib olish",
            callback_data="open_subscription",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession):
    user = await get_or_create_user(
        session=session,
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username or "",
    )

    if not user.onboarded:
        text = (
            "👋 <b>Salom, " + (user.full_name or "do'st") + "!</b>\n\n"
            "Men <b>Intizom AI</b> — sening shaxsiy intizom OS'ing.\n\n"
            "Men sen bilan birga:\n"
            "🎯 Maqsadlaringni rejaga aylantiraman\n"
            "🔥 Streakni saqlayman\n"
            "⚡ XP va darajalar bilan o'sishingni ko'rsataman\n"
            "🧠 Aqlli tahlil qilib, ortga qaytaraman\n\n"
            "<b>Boshlash uchun</b> — bugun nima qilmoqchisan?\n"
            "Ovoz yoki matn bilan ayting:\n"
            "<i>«Soat 7 da turaman, 9 da kitob o'qiyman»</i>"
        )
    else:
        lvl, in_lvl, needed, pct = xp_progress(user.xp or 0)
        rank, emoji = rank_for_level(lvl)
        bar_filled = "▰" * round(pct / 10)
        bar_empty = "▱" * (10 - len(bar_filled))
        name = user.full_name or "do'st"
        text = (
            f"{emoji} <b>Salom, {name}!</b>\n\n"
            f"📊 <b>{rank}</b> — Daraja {lvl}\n"
            f"<code>{bar_filled}{bar_empty}</code> {pct}%\n\n"
            f"🔥 Streak: <b>{user.streak or 0} kun</b>\n"
            f"💎 Discipline: <b>{user.discipline_score or 50}/100</b>\n"
            f"⭐ XP: <b>{user.xp or 0}</b>\n\n"
            "Bugun nima qilamiz?"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_reply_keyboard(),
    )

    is_premium = user_is_premium(user)
    webapp_kb = _webapp_kb(is_premium)
    if webapp_kb:
        if is_premium:
            promo_text = (
                "🚀 <b>Mini App</b> — kalendar, statistika, AI coach.\n"
                f"💎 Premium faol — {days_left(user)} kun qoldi."
            )
        else:
            promo_text = (
                "🚀 <b>Mini App</b> — kalendar, statistika, AI coach.\n\n"
                "🔒 Mini App <b>Premium</b> imkoniyat. Ochish uchun obuna kerak.\n"
                "Tugmani bossangiz, Mini App ichida obuna haqida ma'lumot chiqadi."
            )
        await message.answer(
            promo_text,
            parse_mode="HTML",
            reply_markup=webapp_kb,
        )

    if not user.onboarded:
        user.onboarded = True
        await session.commit()


@router.callback_query(F.data == "home")
async def home_handler(callback: CallbackQuery, session: AsyncSession):
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    lvl, in_lvl, needed, pct = xp_progress(user.xp or 0)
    rank, emoji = rank_for_level(lvl)
    bar_filled = "▰" * round(pct / 10)
    bar_empty = "▱" * (10 - len(bar_filled))

    await callback.message.edit_text(
        f"🏠 <b>Bosh sahifa</b>\n\n"
        f"{emoji} <b>{user.full_name}</b>\n"
        f"📊 {rank} — Daraja {lvl}\n"
        f"<code>{bar_filled}{bar_empty}</code> {pct}%\n\n"
        f"🔥 Streak: <b>{user.streak or 0}</b> kun\n"
        f"💎 Discipline: <b>{user.discipline_score or 50}/100</b>\n"
        f"⭐ XP: <b>{user.xp or 0}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
