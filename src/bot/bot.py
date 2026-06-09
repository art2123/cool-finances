import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import CallbackQuery, ErrorEvent
from redis.asyncio import Redis

from src.bot.handlers import setup_routers
from src.bot.middlewares import DbSessionMiddleware
from src.core.config import get_settings, validate_production_config

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def create_storage():
    settings = get_settings()
    validate_production_config(settings)

    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            redis = Redis.from_url(settings.redis_url)
            await redis.ping()
            if attempt > 1:
                logger.info("Redis connected on attempt %s", attempt)
            return RedisStorage(redis)
        except Exception as exc:
            last_error = exc
            if attempt < 5:
                logger.warning("Redis not ready (attempt %s/5): %s", attempt, exc)
                await asyncio.sleep(2)

    if settings.use_webhook:
        logger.exception("Redis required for webhook FSM")
        raise RuntimeError(
            f"Cannot connect to Redis at {settings.redis_url!r}. "
            "Set REDIS_URL=${{Redis.REDIS_URL}} in Railway Variables "
            "(web and worker services)."
        ) from last_error

    logger.warning("Redis unavailable — using in-memory FSM (local dev only)")
    return MemoryStorage()


def create_dispatcher(storage=None) -> Dispatcher:
    dp = Dispatcher(storage=storage or MemoryStorage())
    dp.update.middleware(DbSessionMiddleware())

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        update = event.update
        if update.callback_query:
            cb: CallbackQuery = update.callback_query
            try:
                await cb.answer("Не удалось выполнить действие. Попробуй ещё раз.", show_alert=True)
            except Exception:
                logger.exception("Failed to answer callback after error")
        logger.exception("Handler error: %s", event.exception)
        return True

    dp.include_router(setup_routers())
    return dp
