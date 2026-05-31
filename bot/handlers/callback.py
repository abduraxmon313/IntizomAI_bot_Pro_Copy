from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.user_service import get_user_by_telegram_id
from bot.services.plan_service import (
    get_plan_by_id, move_plan_to_tomorrow, duplicate_plan_for_tomorrow,
    plan_block_reason,
)
from bot.services.score_service import process_plan_result_full
from bot.services.gamification_service import xp_progress, rank_for_level
from bot.services.coach_service import (
    message_for_level_up, message_for_perfect_day, message_for_comeback,
)
from bot.keyboards.plan_keys import back_to_home_keyboard

router = Router()


def _xp_bar(percent: int, length: int = 10) -> str:
    filled = max(0, min(length, round(percent / 100 * length)))
    return "▰" * filled + "▱" * (length - filled)


@router.callback_query(F.data.startswith("done_"))
async def done_handler(callback: CallbackQuery, session: AsyncSession):
    plan_id = int(callback.data.split("_")[1])

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    plan = await get_plan_by_id(session, plan_id)

    if not plan or not user:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    # Kechagi/oldingi kun rejasini, hamda vaqti hali kelmagan rejani belgilab bo'lmaydi.
    _reason = plan_block_reason(plan.plan_date, plan.scheduled_time)
    if _reason == "past":
        await callback.answer(
            "⏰ O'tib ketgan kundagi rejani belgilab bo'lmaydi.", show_alert=True
        )
        return
    if _reason == "future":
        await callback.answer(
            "⏰ Bu rejaning vaqti hali kelmagan. Vaqti kelgach belgilang.",
            show_alert=True,
        )
        return

    reward = await process_plan_result_full(session, user, plan, is_done=True)

    try:
        lvl, in_lvl, needed, pct = xp_progress(user.xp or 0)
        rank, emoji = rank_for_level(lvl)

        # Premium-his beradigan, toza bayram xabari
        lines = [f"🎯 <b>{plan.title}</b> — bajarildi!", ""]

        row = f"⚡️ <b>+{reward.xp_gained} XP</b>"
        if reward.streak_extended:
            row += f"     🔥 <b>{reward.new_streak} kun</b>"
        lines.append(row)
        lines.append(f"{emoji} <b>{rank}</b> · Daraja {lvl}")
        lines.append(f"<code>{_xp_bar(pct)}</code> {pct}%")
        lines.append(f"💎 Discipline: <b>{reward.discipline_score}/100</b>")

        extras = []
        if reward.leveled_up:
            extras.append(message_for_level_up(reward.new_level))
        if reward.perfect_day:
            extras.append(message_for_perfect_day())
        for ach in reward.new_unlocks:
            extras.append(f"{ach.icon} <b>Yangi yutuq:</b> {ach.title}")

        if extras:
            lines.append("\n━━━━━━━━━━━━━")
            lines.extend(extras)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Ertaga ham qo'shish", callback_data=f"continue_{plan_id}")],
            [
                InlineKeyboardButton(text="📋 Rejalarim", callback_data="my_plans"),
                InlineKeyboardButton(text="🏠 Asosiy", callback_data="home"),
            ],
        ])

        await callback.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        # Xabarni yangilashda xato bo'lsa ham — belgilash allaqachon saqlangan
        pass

    # Toast
    try:
        if reward.leveled_up:
            await callback.answer(f"🎉 Yangi daraja — {reward.new_level}!", show_alert=False)
        elif reward.new_unlocks:
            await callback.answer("🏆 Yangi yutuq ochildi!", show_alert=False)
        else:
            await callback.answer(f"✨ +{reward.xp_gained} XP")
    except Exception:
        pass


@router.callback_query(F.data.startswith("failed_"))
async def failed_handler(callback: CallbackQuery, session: AsyncSession):
    plan_id = int(callback.data.split("_")[1])

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    plan = await get_plan_by_id(session, plan_id)

    if not plan or not user:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    reward = await process_plan_result_full(session, user, plan, is_done=False)

    text = (
        f"💭 <b>{plan.title}</b>\n"
        f"<i>Bugun bo'lmadi — zarari yo'q.</i>\n\n"
        f"Tushish — mag'lubiyat emas. To'xtab qolish — mag'lubiyat. "
        f"Ertaga yana bir imkoniyat bor 💪\n\n"
        f"💎 Discipline: <b>{reward.discipline_score}/100</b>\n"
        f"🔥 Streak: <b>{user.streak} kun</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ertaga ko'chirish", callback_data=f"tomorrow_{plan_id}")],
        [InlineKeyboardButton(text="🏠 Asosiy", callback_data="home")],
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer("Ertaga yana urinamiz 💪")


@router.callback_query(F.data.startswith("tomorrow_"))
async def tomorrow_handler(callback: CallbackQuery, session: AsyncSession):
    plan_id = int(callback.data.split("_")[1])
    plan = await get_plan_by_id(session, plan_id)

    if not plan:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    new_plan = await move_plan_to_tomorrow(session, plan)

    await callback.message.edit_text(
        f"📅 <b>{plan.title}</b> ertaga ko'chirildi.\n\n"
        f"🗓 {new_plan.plan_date.strftime('%d.%m.%Y')}\n"
        f"{f'🕐 {new_plan.scheduled_time}' if new_plan.scheduled_time else '🕐 Vaqtsiz'}\n\n"
        f"⏰ Vaqti kelganda eslatib turaman.",
        parse_mode="HTML",
        reply_markup=back_to_home_keyboard(),
    )
    await callback.answer("Ertaga ko'chirildi 📅")


@router.callback_query(F.data.startswith("continue_"))
async def continue_handler(callback: CallbackQuery, session: AsyncSession):
    plan_id = int(callback.data.split("_")[1])
    plan = await get_plan_by_id(session, plan_id)

    if not plan:
        await callback.answer("Reja topilmadi!", show_alert=True)
        return

    new_plan = await duplicate_plan_for_tomorrow(session, plan)

    await callback.message.edit_text(
        f"🔁 <b>Zo'r — odat shakllanmoqda!</b>\n\n"
        f"📌 {plan.title} — ertaga ham davom etadi.\n\n"
        f"🗓 {new_plan.plan_date.strftime('%d.%m.%Y')}\n"
        f"{f'🕐 {new_plan.scheduled_time}' if new_plan.scheduled_time else '🕐 Vaqtsiz'}",
        parse_mode="HTML",
        reply_markup=back_to_home_keyboard(),
    )
    await callback.answer("Ertaga ham qo'shildi 🔁")
