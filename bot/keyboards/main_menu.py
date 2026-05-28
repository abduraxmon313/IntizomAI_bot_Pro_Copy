from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Rejalarim", callback_data="my_plans"),
            InlineKeyboardButton(text="➕ Reja qo'sh", callback_data="add_plan"),
        ],
        [
            InlineKeyboardButton(text="📊 Hisobot", callback_data="report"),
        ]
    ])