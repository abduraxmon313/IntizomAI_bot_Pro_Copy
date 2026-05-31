from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from bot.config import TIMEZONE
from bot.services.user_service import get_user_by_telegram_id
from bot.services.plan_service import get_today_plans
from bot.services.score_service import get_today_score
from bot.services.admin_service import get_user_status
from bot.models.plan import Plan, PlanStatus
from bot.keyboards.plan_keys import back_to_home_keyboard

router = Router()

UZ_WEEKDAYS = [
    "Dushanba", "Seshanba", "Chorshanba", "Payshanba",
    "Juma", "Shanba", "Yakshanba",
]


def _progress_bar(done: int, total: int, length: int = 10) -> str:
    """To'ladigan progress chizig'i: ▰▰▰▱▱▱▱▱▱▱"""
    if total <= 0:
        return "▱" * length
    filled = max(0, min(length, round(done * length / total)))
    return "▰" * filled + "▱" * (length - filled)


def _closing_line(done: int, total: int) -> str:
    """Bajarish darajasiga qarab premium motivatsion yakun."""
    if total <= 0:
        return "🌱 <i>Bitta kichik reja qo'shib, kuningni boshla.</i>"
    pct = done * 100 / total
    if pct >= 100:
        return "✨ <i>Mukammal kun! Hammasini uddalading.</i>"
    if pct >= 60:
        return "💪 <i>Zo'r ketyapsan — yakuniga yetkaz!</i>"
    if done > 0:
        return "🌱 <i>Yaxshi boshlanish — qolganini ham uddalaysan.</i>"
    return "⏳ <i>Hali ulgurasan. Bittadan boshla 🚀</i>"


async def build_report_text(session, user) -> str:
    plans = await get_today_plans(session, user)

    done = [p for p in plans if p.status == PlanStatus.done]
    failed = [p for p in plans if p.status == PlanStatus.failed]
    pending = [p for p in plans if p.status == PlanStatus.pending]

    # Bugungi ballarni hisoblash (Tashkent vaqti bo'yicha)
    today_score = await get_today_score(session, user)
    status = get_user_status(user.total_score, user.streak)

    now = datetime.now(TIMEZONE)
    today_str = now.strftime('%d.%m.%Y')
    weekday = UZ_WEEKDAYS[now.weekday()]

    total = len(plans)
    done_n = len(done)
    pct = round(done_n * 100 / total) if total else 0

    text = "📊 <b>Bugungi hisobot</b>\n"
    text += f"🗓 {today_str} · {weekday}\n\n"

    if total:
        text += f"<code>{_progress_bar(done_n, total)}</code>  {done_n}/{total} · {pct}%\n\n"

    if done:
        text += f"✅ <b>Bajarildi · {len(done)}</b>\n"
        for p in done:
            text += f"   • {p.title}  <i>+{p.score_value} XP</i>\n"
        text += "\n"

    if failed:
        text += f"❌ <b>Bajarilmadi · {len(failed)}</b>\n"
        for p in failed:
            text += f"   • {p.title}\n"
        text += "\n"

    if pending:
        text += f"⬜️ <b>Qoldi · {len(pending)}</b>\n"
        for p in pending:
            time_str = p.scheduled_time if p.scheduled_time else "vaqtsiz"
            text += f"   • {p.title}  <i>{time_str}</i>\n"
        text += "\n"

    if not plans:
        text += "📭 Bugun hali reja yo'q.\n\n"

    text += "━━━━━━━━━━━━━\n"
    text += f"⚡️ Bugungi XP: <b>{today_score:+d}</b>   🔥 <b>{user.streak} kun</b>\n"
    text += f"🏆 Umumiy: <b>{user.total_score} XP</b>   ·   {status}\n\n"
    text += _closing_line(done_n, total)

    return text


# Reply keyboard tugmasi
@router.message(F.text == "📈 Hisobot")
async def report_message(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)

    if not user:
        await message.answer("Iltimos /start bosing.")
        return

    text = await build_report_text(session, user)
    await message.answer(text, parse_mode="HTML")


# Inline callback
@router.callback_query(F.data == "report")
async def report_callback(callback: CallbackQuery, session: AsyncSession):
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if not user:
        await callback.answer("Xatolik!", show_alert=True)
        return

    text = await build_report_text(session, user)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_home_keyboard()
    )
    await callback.answer()