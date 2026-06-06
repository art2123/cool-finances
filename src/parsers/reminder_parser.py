import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from src.domain.enums import ReminderRecurrence


@dataclass
class ReminderDraft:
    title: str
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    recurrence: ReminderRecurrence = ReminderRecurrence.MONTHLY
    day_of_month: Optional[int] = None
    remind_days_before: int = 3
    specific_date: Optional[date] = None
    message: Optional[str] = None


def parse_reminder_text(text: str) -> ReminderDraft:
    lower = text.lower()
    draft = ReminderDraft(title="Платёж")

    days_before_match = re.search(r"за\s+(\d+)\s+дн", lower)
    if days_before_match:
        draft.remind_days_before = int(days_before_match.group(1))

    day_match = re.search(r"(\d{1,2})[-го]*\s*(?:числ|го|е)", lower)
    if day_match:
        draft.day_of_month = int(day_match.group(1))
        draft.recurrence = ReminderRecurrence.MONTHLY

    amount_match = re.search(r"(\d[\d\s]*)\s*(?:динар|rsd|евро|eur)?", lower)
    if amount_match:
        draft.amount = Decimal(amount_match.group(1).replace(" ", ""))

    if "квартал" in lower:
        draft.recurrence = ReminderRecurrence.QUARTERLY
        draft.title = "Налоги"
    elif "аренд" in lower or "квартир" in lower:
        draft.title = "Аренда"
    elif "налог" in lower:
        draft.title = "Налоги"
    elif "кредит" in lower or "visa" in lower:
        draft.title = "Кредит"

    if "rsd" in lower or "динар" in lower:
        draft.currency = "RSD"
    elif "eur" in lower or "евро" in lower:
        draft.currency = "EUR"

    return draft


def compute_next_remind_at(draft: ReminderDraft, tz: str = "Europe/Belgrade") -> datetime:
    today = date.today()
    if draft.specific_date:
        target = draft.specific_date
    elif draft.day_of_month:
        target = today.replace(day=min(draft.day_of_month, 28))
        if target <= today:
            if today.month == 12:
                target = target.replace(year=today.year + 1, month=1)
            else:
                target = target.replace(month=today.month + 1)
    else:
        target = today + timedelta(days=7)

    remind_date = target - timedelta(days=draft.remind_days_before)
    if remind_date < today:
        remind_date = today
    return datetime.combine(remind_date, time(9, 0))
