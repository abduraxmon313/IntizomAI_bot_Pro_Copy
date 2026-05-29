import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from webapp.routes import goals, plans, stats, subscription

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


async def run_bot():
    try:
        from bot.main import main
        logger.info("🤖 Bot ishga tushmoqda...")
        await main()
    except asyncio.CancelledError:
        logger.info("🛑 Bot to'xtatildi")
    except Exception as e:
        logger.error(f"❌ Bot xatosi: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(run_bot())
    logger.info("🌐 FastAPI server tayyor")
    yield
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Intizom AI Web App API",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plans.router, prefix="/api/webapp")
app.include_router(goals.router, prefix="/api/webapp")
app.include_router(stats.router, prefix="/api/webapp")
app.include_router(subscription.router, prefix="/api/webapp")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")
