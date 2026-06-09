from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import RecurrencePeriod, ReminderRecurrence
from src.models.user_reminder import UserReminder
from src.parsers.reminder_parser import ReminderDraft, compute_next_remind_at
from src.repositories import recurring_repo, reminder_repo


async def create_from_draft(
    session: AsyncSession,
    user_id: int,
    draft: ReminderDraft,
    account_id: Optional[int] = None,
) -> UserReminder:
    next_at = compute_next_remind_at(draft)
    reminder = await reminder_repo.create_reminder(
        session,
        user_id=user_id,
        title=draft.title,
        message=draft.message or f"Напоминание: {draft.title}",
        amount=draft.amount,
        currency=draft.currency,
        account_id=account_id,
        recurrence=draft.recurrence,
        day_of_month=draft.day_of_month,
        remind_days_before=draft.remind_days_before,
        specific_date=draft.specific_date,
        next_remind_at=next_at,
    )

    if draft.recurrence == ReminderRecurrence.MONTHLY and draft.day_of_month and draft.amount:
        from datetime import date as dt

        next_date = dt.today().replace(day=min(draft.day_of_month, 28))
        if next_date <= dt.today():
            month = next_date.month + 1
            year = next_date.year
            if month > 12:
                month = 1
                year += 1
            next_date = next_date.replace(year=year, month=month)
        if account_id:
            await recurring_repo.create_recurring(
                session,
                user_id=user_id,
                account_id=account_id,
                name=draft.title,
                amount=draft.amount,
                currency=draft.currency or "RSD",
                period=RecurrencePeriod.MONTHLY,
                next_date=next_date,
                is_mandatory=True,
            )
    return reminder


def advance_reminder(reminder: UserReminder) -> None:
    reminder.last_sent_at = datetime.utcnow()
    if reminder.recurrence == ReminderRecurrence.ONCE:
        reminder.is_active = False
        return
    if reminder.recurrence == ReminderRecurrence.MONTHLY:
        reminder.next_remind_at = reminder.next_remind_at + timedelta(days=30)
    elif reminder.recurrence == ReminderRecurrence.QUARTERLY:
        reminder.next_remind_at = reminder.next_remind_at + timedelta(days=90)
    else:
        reminder.next_remind_at = reminder.next_remind_at + timedelta(days=30)


def format_reminders_list(reminders: list) -> str:
    if not reminders:
        return "Напоминаний нет. Напиши: «напомни за 5 дней до 25-го про аренду 35000»"
    lines = ["*Напоминания:*"]
    for r in reminders:
        status = "✅" if r.is_active else "⏸"
        amt = f" {r.amount:,.0f} {r.currency}" if r.amount else ""
        lines.append(f"{status} {r.title}{amt} — за {r.remind_days_before}д до, след. {r.next_remind_at.strftime('%d.%m.%Y')}")
    return "\n".join(lines)
