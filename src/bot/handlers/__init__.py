from aiogram import Router

from src.bot.handlers import (
    accounts,
    advisor,
    batch_expenses,
    common,
    conversions,
    credits,
    expenses,
    family,
    fsm_fallback,
    goals,
    history,
    photos,
    reminders,
    reports,
    transfers,
)


def setup_routers() -> Router:
    router = Router()
    router.include_router(common.router)
    router.include_router(family.router)
    router.include_router(accounts.router)
    router.include_router(credits.router)
    router.include_router(advisor.router)
    router.include_router(reminders.router)
    router.include_router(transfers.router)
    router.include_router(conversions.router)
    router.include_router(goals.router)
    router.include_router(reports.router)
    router.include_router(history.router)
    router.include_router(batch_expenses.router)
    router.include_router(photos.router)
    router.include_router(expenses.router)  # last: free-text fallback
    router.include_router(fsm_fallback.router)  # catch-all for unhandled FSM input
    return router
