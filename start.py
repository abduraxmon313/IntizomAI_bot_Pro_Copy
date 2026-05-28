import asyncio
import os
import logging
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def start_bot():
    from bot.main import main
    logger.info("🤖 Bot ishga tushmoqda...")
    await main()


async def start_server():
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🌐 FastAPI server port {port} da ishga tushmoqda...")
    config = uvicorn.Config(
        "webapp.app:app",
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(
        start_bot(),
        start_server(),
    )


if __name__ == "__main__":
    asyncio.run(main())
