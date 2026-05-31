"""
Yagona kirish nuqtasi (local va Railway uchun).

MUHIM: bot'ni FAQAT bitta joyda ishga tushiramiz. `webapp/app.py` ning
`lifespan` qismi server ko'tarilganda bot'ni avtomatik ishga tushiradi.
Shu sabab bu fayl FAQAT uvicorn serverni ishga tushiradi — aks holda bot
ikki marta `start_polling` qilib, Telegram 409 Conflict ("terminated by
other getUpdates request") xatosini berardi.

Railway/Procfile to'g'ridan-to'g'ri `uvicorn webapp.app:app` ishlatadi;
bu fayl esa lokal ishga tushirish (`python start.py`) qulayligi uchun.
"""
import logging
import os

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🌐 Server port {port} da ishga tushmoqda (bot lifespan orqali)...")
    uvicorn.run(
        "webapp.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
