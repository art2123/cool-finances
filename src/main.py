import asyncio
import logging
import sys

from src.bot.bot import create_bot, create_dispatcher, create_storage
from src.core.database import init_db
from src.core.database import async_session_factory
from src.repositories.category_repo import ensure_system_categories

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_polling() -> None:
    await init_db()
    async with async_session_factory() as session:
        await ensure_system_categories(session)
        await session.commit()

    bot = create_bot()
    storage = await create_storage()
    dp = create_dispatcher(storage)
    logger.info("Starting polling...")
    await dp.start_polling(bot)


def run_worker() -> None:
    from arq import run_worker

    from src.core.config import get_settings
    from src.workers.reminder_worker import WorkerSettings

    token = get_settings().bot_token
    if not token or ":" not in token:
        logger.error("BOT_TOKEN is missing or invalid. Set it in Railway Variables for the worker service.")
        sys.exit(1)

    logger.info("Starting ARQ worker...")
    run_worker(WorkerSettings)


def main() -> None:
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "poll":
            asyncio.run(run_polling())
            return
        if cmd == "worker":
            run_worker()
            return

    import os
    import uvicorn
    from src.core.config import get_settings

    settings = get_settings()
    port = int(os.getenv("PORT", settings.app_port))
    uvicorn.run(
        "src.api.app:app",
        host=settings.app_host,
        port=port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
