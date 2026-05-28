from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin_service import (
    is_admin, get_all_users, get_users_count,
    get_all_admins, add_admin, remove_admin,
    get_user_plan_stats, get_user_status
)
from bot.services.user_service import get_user_by_telegram_id
from bot.keyboards.admin_keys import (
    admin_main_keyboard, admin_users_keyboard,
    admin_users_list_keyboard, admin_admins_keyboard,
    back_to_admin_keyboard, back_to_users_keyboard
)

router = Router()


class AdminState(StatesGroup):
    waiting_admin_id_add = State()
    waiting_admin_id_remove = State()
    # Broadcast
    broadcast_choosing = State()      # Umumiy yoki ID
    broadcast_waiting_id = State()    # ID kutish
    broadcast_waiting_text = State()  # Xabar matni kutish


def broadcast_type_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Barcha userlarga", callback_data="broadcast_all"),
            InlineKeyboardButton(text="👤 ID orqali", callback_data="broadcast_by_id"),
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")
        ]
    ])


def broadcast_confirm_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="broadcast_send"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="admin_panel"),
        ]
    ])


# ===================== KIRISH =====================

@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession):
    if not await is_admin(session, message.from_user.id):
        await message.answer("❌ Sizda admin huquqi yo'q.")
        return

    await message.answer(
        "🛡 <b>Admin Panel</b>\n\nKerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "🛡 <b>Admin Panel</b>\n\nKerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )
    await callback.answer()


# ===================== USERLAR =====================

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.message.edit_text(
        "👥 <b>Userlar bo'limi</b>\n\nNima qilamiz?",
        parse_mode="HTML",
        reply_markup=admin_users_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_users_count")
async def admin_users_count(callback: CallbackQuery, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    from bot.services.admin_service import get_detailed_users_stats
    stats = await get_detailed_users_stats(session)

    # Top userlar
    top_text = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, user in enumerate(stats["top_users"]):
        name = user.full_name if user.full_name else "Noma'lum"
        top_text += f"{medals[i]} {name} — <b>{user.total_score} ball</b>\n"

    sc = stats["status_counts"]
    osishda_count = sc.get("📈 O'sishda", 0)

    text = (
        f"🔢 <b>Userlar statistikasi</b>\n\n"
        f"👥 Jami: <b>{stats['total']} ta</b>\n"
        f"✅ Aktiv (rejasi bor): <b>{stats['active']} ta</b>\n"
        f"😴 Harakatsiz: <b>{stats['inactive']} ta</b>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 <b>Statuslar bo'yicha:</b>\n"
        f"🏆 Ustoz: <b>{sc['🏆 Ustoz']} ta</b>\n"
        f"💎 Intizomli: <b>{sc['💎 Intizomli']} ta</b>\n"
        f"🔥 Focused: <b>{sc['🔥 Focused']} ta</b>\n"
        f"📈 O'sishda: <b>{osishda_count} ta</b>\n"
        f"🌱 Yangi boshlovchi: <b>{sc['🌱 Yangi boshlovchi']} ta</b>\n"
        f"😴 Harakatsiz: <b>{sc['😴 Harakatsiz']} ta</b>\n\n"
    )

    if stats["top_users"]:
        text += f"━━━━━━━━━━━━━━━\n🏅 <b>Top userlar:</b>\n{top_text}"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_users_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: CallbackQuery, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    users = await get_all_users(session)

    if not users:
        await callback.message.edit_text(
            "👥 Hozircha hech qanday user yo'q.",
            reply_markup=back_to_admin_keyboard()
        )
        return

    await callback.message.edit_text(
        f"👥 <b>Barcha userlar</b> ({len(users)} ta)\n\nUserni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_users_list_keyboard(users, page=0)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_users_page_"))
async def admin_users_page(callback: CallbackQuery, session: AsyncSession):
    page = int(callback.data.split("_")[-1])
    users = await get_all_users(session)

    await callback.message.edit_text(
        f"👥 <b>Barcha userlar</b> ({len(users)} ta)\n\nUserni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_users_list_keyboard(users, page=page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_"))
async def admin_user_detail(callback: CallbackQuery, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])

    from sqlalchemy import select
    from bot.models.user import User
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        await callback.answer("User topilmadi!", show_alert=True)
        return

    stats = await get_user_plan_stats(session, user)
    status = get_user_status(user.total_score, user.streak)

    username_str = f"@{user.username}" if user.username else "Yoq"
    reg_date = user.created_at.strftime("%d.%m.%Y")
    full_name = user.full_name if user.full_name else "Noma'lum"

    text = (
        f"👤 <b>User ma'lumotlari</b>\n\n"
        f"📛 Ismi: <b>{full_name}</b>\n"
        f"🔗 Username: <b>{username_str}</b>\n"
        f"🆔 Telegram ID: <b>{user.telegram_id}</b>\n"
        f"📅 Ulangan sana: <b>{reg_date}</b>\n"
        f"📊 Status: <b>{status}</b>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 Jami rejalar: <b>{stats['total_plans']}</b>\n"
        f"✅ Bajarilgan: <b>{stats['done']}</b>\n"
        f"❌ Bajarilmagan: <b>{stats['failed']}</b>\n"
        f"⏳ Kutilmoqda: <b>{stats['pending']}</b>\n\n"
        f"⭐ Umumiy ball: <b>{user.total_score}</b>\n"
        f"🔥 Streak: <b>{user.streak} kun</b>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_users_keyboard()
    )
    await callback.answer()


# ===================== ADMINLAR =====================

@router.callback_query(F.data == "admin_admins")
async def admin_admins(callback: CallbackQuery, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.message.edit_text(
        "🛡 <b>Adminlar bo'limi</b>\n\nNima qilamiz?",
        parse_mode="HTML",
        reply_markup=admin_admins_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_list")
async def admin_list(callback: CallbackQuery, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    admins = await get_all_admins(session)

    if not admins:
        text = "🛡 <b>Adminlar ro'yxati</b>\n\nHozircha qo'shimcha admin yo'q."
    else:
        text = f"🛡 <b>Adminlar ro'yxati</b> ({len(admins)} ta)\n\n"
        for i, adm in enumerate(admins, 1):
            added = adm.added_at.strftime("%d.%m.%Y")
            adm_name = adm.full_name if adm.full_name else "Noma'lum"
            text += f"{i}. <b>{adm_name}</b>\n"
            text += f"   ID: {adm.telegram_id} | {added}\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_admins_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.message.edit_text(
        "➕ <b>Admin qo'shish</b>\n\n"
        "Yangi adminning Telegram ID sini yuboring:\n\n"
        "<i>ID ni bilish uchun @userinfobot ga /start yuboring</i>",
        parse_mode="HTML",
        reply_markup=back_to_admin_keyboard()
    )
    await state.set_state(AdminState.waiting_admin_id_add)
    await callback.answer()


@router.message(AdminState.waiting_admin_id_add)
async def admin_add_process(message: Message, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, message.from_user.id):
        return

    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam yuboring:")
        return

    try:
        chat = await message.bot.get_chat(new_admin_id)
        full_name = chat.full_name if chat.full_name else "Noma'lum"
    except Exception:
        full_name = "Noma'lum"

    admin_obj = await add_admin(session, new_admin_id, full_name)

    if admin_obj:
        await message.answer(
            f"✅ <b>{full_name}</b> admin qilindi!\nID: {new_admin_id}",
            parse_mode="HTML",
            reply_markup=admin_admins_keyboard()
        )
    else:
        await message.answer(
            "⚠️ Bu user allaqachon admin!",
            reply_markup=admin_admins_keyboard()
        )
    await state.clear()


@router.callback_query(F.data == "admin_remove")
async def admin_remove_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await callback.message.edit_text(
        "➖ <b>Admin o'chirish</b>\n\n"
        "O'chiriladigan adminning Telegram ID sini yuboring:",
        parse_mode="HTML",
        reply_markup=back_to_admin_keyboard()
    )
    await state.set_state(AdminState.waiting_admin_id_remove)
    await callback.answer()


@router.message(AdminState.waiting_admin_id_remove)
async def admin_remove_process(message: Message, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, message.from_user.id):
        return

    try:
        remove_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam yuboring:")
        return

    from bot.config import ADMIN_ID
    if remove_id == ADMIN_ID:
        await message.answer(
            "❌ Super adminni o'chirib bo'lmaydi!",
            reply_markup=admin_admins_keyboard()
        )
        await state.clear()
        return

    success = await remove_admin(session, remove_id)

    if success:
        await message.answer(
            f"✅ Admin (ID: {remove_id}) o'chirildi!",
            reply_markup=admin_admins_keyboard()
        )
    else:
        await message.answer(
            "⚠️ Bu ID da admin topilmadi!",
            reply_markup=admin_admins_keyboard()
        )
    await state.clear()


# ===================== BROADCASTING =====================

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    count = await get_users_count(session)

    await callback.message.edit_text(
        f"📢 <b>Xabar yuborish</b>\n\n"
        f"👥 Jami userlar: <b>{count} ta</b>\n\n"
        f"Kimga yuboramiz?",
        parse_mode="HTML",
        reply_markup=broadcast_type_keyboard()
    )
    await state.set_state(AdminState.broadcast_choosing)
    await callback.answer()


# Barcha userlarga
@router.callback_query(F.data == "broadcast_all")
async def broadcast_all_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await state.update_data(broadcast_target="all", target_id=None)
    await state.set_state(AdminState.broadcast_waiting_text)

    await callback.message.edit_text(
        "📢 <b>Barcha userlarga xabar</b>\n\n"
        "Xabar matnini yuboring:\n\n"
        "<i>HTML format ishlaydi:\n"
        "&lt;b&gt;bold&lt;/b&gt; → <b>bold</b>\n"
        "&lt;i&gt;italic&lt;/i&gt; → <i>italic</i>\n"
        "&lt;u&gt;underline&lt;/u&gt; → <u>underline</u>\n"
        "&lt;code&gt;code&lt;/code&gt; → <code>code</code></i>",
        parse_mode="HTML",
        reply_markup=back_to_admin_keyboard()
    )
    await callback.answer()


# ID orqali
@router.callback_query(F.data == "broadcast_by_id")
async def broadcast_by_id_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    await state.set_state(AdminState.broadcast_waiting_id)

    await callback.message.edit_text(
        "👤 <b>ID orqali xabar</b>\n\n"
        "Telegram ID ni yuboring:",
        parse_mode="HTML",
        reply_markup=back_to_admin_keyboard()
    )
    await callback.answer()


# ID kiritish
@router.message(AdminState.broadcast_waiting_id)
async def broadcast_id_received(message: Message, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, message.from_user.id):
        return

    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Faqat raqam yuboring:")
        return

    # User mavjudligini tekshirish
    try:
        chat = await message.bot.get_chat(target_id)
        name = chat.full_name if chat.full_name else "Noma'lum"
    except Exception:
        await message.answer(
            "❌ Bu ID da user topilmadi. Tekshirib qayta yuboring:",
            reply_markup=back_to_admin_keyboard()
        )
        return

    await state.update_data(broadcast_target="id", target_id=target_id, target_name=name)
    await state.set_state(AdminState.broadcast_waiting_text)

    await message.answer(
        f"👤 <b>{name}</b> (ID: {target_id})\n\n"
        f"Xabar matnini yuboring:\n\n"
        f"<i>HTML format ishlaydi:\n"
        f"&lt;b&gt;bold&lt;/b&gt; → <b>bold</b>\n"
        f"&lt;i&gt;italic&lt;/i&gt; → <i>italic</i>\n"
        f"&lt;u&gt;underline&lt;/u&gt; → <u>underline</u>\n"
        f"&lt;code&gt;code&lt;/code&gt; → <code>code</code></i>",
        parse_mode="HTML",
        reply_markup=back_to_admin_keyboard()
    )


# Xabar matni keldi — preview ko'rsatish
@router.message(AdminState.broadcast_waiting_text)
async def broadcast_text_received(message: Message, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, message.from_user.id):
        return

    data = await state.get_data()
    target = data.get("broadcast_target")
    target_id = data.get("target_id")
    target_name = data.get("target_name", "")

    await state.update_data(broadcast_text=message.text)

    if target == "all":
        count = await get_users_count(session)
        preview_header = f"📢 <b>Barcha {count} ta userlarga yuboriladi</b>\n\n"
    else:
        preview_header = f"👤 <b>{target_name}</b> ga yuboriladi\n\n"

    # Preview ko'rsatish
    await message.answer(
        f"👁 <b>Preview:</b>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{message.text}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{preview_header}"
        f"Yuborishni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=broadcast_confirm_keyboard()
    )


# Yuborish tasdiqlandi
@router.callback_query(F.data == "broadcast_send")
async def broadcast_send_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await is_admin(session, callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    data = await state.get_data()
    target = data.get("broadcast_target")
    target_id = data.get("target_id")
    broadcast_text = data.get("broadcast_text", "")

    await state.clear()

    final_text = f"📢 <b>Intizom AI:</b>\n\n{broadcast_text}"

    if target == "id":
        # Bitta usergа
        try:
            await callback.bot.send_message(
                chat_id=target_id,
                text=final_text,
                parse_mode="HTML"
            )
            await callback.message.edit_text(
                f"✅ <b>Xabar yuborildi!</b>\n\nID: {target_id}",
                parse_mode="HTML",
                reply_markup=back_to_admin_keyboard()
            )
        except Exception as e:
            await callback.message.edit_text(
                f"❌ Xabar yuborishda xatolik: {str(e)}",
                reply_markup=back_to_admin_keyboard()
            )
    else:
        # Barcha userlarga
        users = await get_all_users(session)
        sent = 0
        failed = 0

        await callback.message.edit_text("⏳ Yuborilmoqda...")

        for user in users:
            try:
                await callback.bot.send_message(
                    chat_id=user.telegram_id,
                    text=final_text,
                    parse_mode="HTML"
                )
                sent += 1
            except Exception:
                failed += 1

        await callback.message.edit_text(
            f"✅ <b>Xabar yuborildi!</b>\n\n"
            f"✅ Muvaffaqiyatli: <b>{sent} ta</b>\n"
            f"❌ Yuborilmadi: <b>{failed} ta</b>",
            parse_mode="HTML",
            reply_markup=back_to_admin_keyboard()
        )

    await callback.answer()