import logging
from contextlib import asynccontextmanager
from typing import Optional

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from src.bot.bot import create_bot, create_dispatcher, create_storage
from src.core.config import get_settings
from src.core.database import async_session_factory, init_db
from src.repositories.category_repo import ensure_system_categories

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
bot = None
dp = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    bot = create_bot()
    storage = await create_storage()
    dp = create_dispatcher(storage)

    await init_db()
    async with async_session_factory() as session:
        await ensure_system_categories(session)
        await session.commit()

    if settings.use_webhook:
        port = settings.app_port
        base = settings.webhook_url.rstrip("/")
        webhook_url = f"{base}/webhook/{settings.bot_token}"
        await bot.set_webhook(url=webhook_url, secret_token=settings.webhook_secret or None)
        logger.info("Webhook set: %s", webhook_url)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("No WEBHOOK_URL — use polling: python -m src.main poll")

    yield
    await bot.session.close()


app = FastAPI(title="Cool Finances Bot", version="1.5.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.5.0"}


@app.post("/webhook/{token}")
async def webhook(
    token: str,
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> dict:
    if token != settings.bot_token:
        raise HTTPException(status_code=403, detail="Invalid token")
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    if bot is None or dp is None:
        raise HTTPException(status_code=503, detail="Bot not ready")

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
