from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Mening statusim"),
                KeyboardButton(text="📋 Rejalarim"),
            ],
            [
                KeyboardButton(text="📈 Hisobot"),
                KeyboardButton(text="➕ Reja qo'shish"),
            ]
        ],
        resize_keyboard=True,
        persistent=True
    )