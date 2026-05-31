"""
Yengil in-memory rate limiter — bot tomonidagi qimmat AI chaqiruvlarini
(Whisper transkripsiya + GPT tahlil) suiiste'moldan himoya qiladi.

Muammo: ovozli/matnli xabar kelganda bot DARHOL OpenAI ga so'rov yuboradi
(transcribe_voice / extract_plans_from_text). Limit esa faqat rejani
tasdiqlashda tekshirilardi — ya'ni foydalanuvchi hech narsa tasdiqlamasdan
cheksiz xabar yuborib OpenAI hisobini "yoqib" yuborishi mumkin edi.

Bu modul foydalanuvchi bo'yicha (telegram_id) sirpanuvchi-oyna (sliding window)
limiti qo'yadi. DB ustun qo'shishni talab qilmaydi (bitta instans uchun yetarli).
"""
from __future__ import annotations

import time

# Foydalanuvchi bo'yicha urinishlar vaqtlari (telegram_id -> [timestamp, ...])
_hits: dict[int, list[float]] = {}

# Bepul foydalanuvchi: oynada (WINDOW soniya) ruxsat etilgan AI tahlillar soni
FREE_AI_ANALYSIS_PER_WINDOW = 12
# Premium foydalanuvchi: ancha yuqori (lekin baribir runaway/abuse'dan himoya)
PREMIUM_AI_ANALYSIS_PER_WINDOW = 40
WINDOW_SECONDS = 600  # 10 daqiqa


def allow_ai_analysis(user_id: int, is_premium: bool = False) -> bool:
    """
    True qaytarsa — AI tahliliga ruxsat (va urinish hisobga olinadi).
    False qaytarsa — limit oshib ketgan, OpenAI ga so'rov YUBORILMASLIGI kerak.
    """
    now = time.time()
    window_start = now - WINDOW_SECONDS
    limit = PREMIUM_AI_ANALYSIS_PER_WINDOW if is_premium else FREE_AI_ANALYSIS_PER_WINDOW

    bucket = _hits.get(user_id)
    if bucket is None:
        bucket = []
        _hits[user_id] = bucket

    # Eskirgan yozuvlarni tozalaymiz
    while bucket and bucket[0] < window_start:
        bucket.pop(0)

    if len(bucket) >= limit:
        return False

    bucket.append(now)

    # Xotira o'smasligi uchun vaqti-vaqti bilan tozalash
    if len(_hits) > 10000:
        for k in list(_hits.keys()):
            b = _hits.get(k)
            if not b or b[-1] < window_start:
                _hits.pop(k, None)

    return True


def seconds_until_reset(user_id: int) -> int:
    """Limit bo'shashiga taxminan necha soniya qolgani (xabar uchun)."""
    bucket = _hits.get(user_id)
    if not bucket:
        return 0
    return max(0, int(WINDOW_SECONDS - (time.time() - bucket[0])))
