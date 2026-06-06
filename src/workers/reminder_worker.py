import logging
from datetime import datetime

from arq import cron
from arq.connections import RedisSettings

from src.bot.bot import create_bot
from src.core.config import get_settings
from src.core.database import async_session_factory
from src.repositories import account_repo, reminder_repo
from src.services import balance_service
from src.services.reminder_service import advance_reminder

logger = logging.getLogger(__name__)


async def send_due_reminders(ctx: dict) -> None:
    settings = get_settings()
    bot = create_bot()
    now = datetime.utcnow()

    async with async_session_factory() as session:
        due = await reminder_repo.get_due_reminders(session, now)
        for reminder in due:
            from src.models.user import User
            from sqlalchemy import select

            result = await session.execute(select(User).where(User.id == reminder.user_id))
            user = result.scalar_one_or_none()
            if not user:
                continue

            balance_line = ""
            if reminder.account_id:
                acc = await account_repo.get_account_by_id(session, user.id, reminder.account_id)
                if acc:
                    balance_line = f"\nСчёт {acc.name}: {balance_service.format_money(acc.balance, acc.currency)}"

            amount_line = ""
            if reminder.amount and reminder.currency:
                amount_line = f"\nСумма: {reminder.amount:,.0f} {reminder.currency}"

            text = f"🔔 {reminder.title}{amount_line}{balance_line}"
            try:
                await bot.send_message(user.telegram_id, text)
                advance_reminder(reminder)
            except Exception as e:
                logger.error("Failed to send reminder %s: %s", reminder.id, e)
        await session.commit()
    await bot.session.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [send_due_reminders]
    cron_jobs = [cron(send_due_reminders, minute={0, 30})]
