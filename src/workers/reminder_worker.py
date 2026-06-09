import logging
from datetime import datetime

from arq import cron
from arq.connections import RedisSettings

from src.bot.bot import create_bot
from src.core.config import get_settings
from src.core.database import async_session_factory
from src.repositories import account_repo, reminder_repo, user_repo
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
            telegram_ids = await user_repo.get_family_telegram_ids(session, reminder.user_id)
            if not telegram_ids:
                continue

            balance_line = ""
            if reminder.account_id:
                acc = await account_repo.get_account_by_id(
                    session, reminder.user_id, reminder.account_id
                )
                if acc:
                    balance_line = f"\nСчёт {acc.name}: {balance_service.format_money(acc.balance, acc.currency)}"

            amount_line = ""
            if reminder.amount and reminder.currency:
                amount_line = f"\nСумма: {reminder.amount:,.0f} {reminder.currency}"

            text = f"🔔 {reminder.title}{amount_line}{balance_line}"
            sent = False
            for telegram_id in telegram_ids:
                try:
                    await bot.send_message(telegram_id, text)
                    sent = True
                except Exception as e:
                    logger.error(
                        "Failed to send reminder %s to %s: %s", reminder.id, telegram_id, e
                    )
            if sent:
                advance_reminder(reminder)
        await session.commit()
    await bot.session.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [send_due_reminders]
    cron_jobs = [cron(send_due_reminders, minute={0, 30})]
