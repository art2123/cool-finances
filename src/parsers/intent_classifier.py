import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.domain.enums import UserIntent


@dataclass
class ClassifiedIntent:
    intent: UserIntent
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    account_hint: Optional[str] = None
    period_hint: Optional[str] = None


def classify_intent(text: str) -> ClassifiedIntent:
    lower = text.lower().strip()

    if re.search(r"напомни|напоминан|remind", lower):
        return ClassifiedIntent(intent=UserIntent.REMINDER)
    if re.search(r"перевед|перевод|transfer", lower):
        return ClassifiedIntent(intent=UserIntent.TRANSFER)
    if re.search(r"что будет|если.*закин|если.*доплат|what.?if|whatif", lower):
        return ClassifiedIntent(intent=UserIntent.WHAT_IF, amount=_extract_amount(lower))
    if re.search(r"могу ли|позволить|можно ли купить|можно купить|iphone|купить.*в след", lower):
        return ClassifiedIntent(intent=UserIntent.AFFORDABILITY, amount=_extract_amount(lower))
    if re.search(r"сколько.*отлож|сколько смогу|если потрачу", lower):
        return ClassifiedIntent(intent=UserIntent.SAVINGS_PROJECTION, amount=_extract_amount(lower))
    if re.search(r"процент|теряю|/interest|переплат", lower):
        return ClassifiedIntent(intent=UserIntent.INTEREST)
    if re.search(r"прогноз|/forecast|свободн.*денег", lower):
        return ClassifiedIntent(intent=UserIntent.FORECAST)
    if re.search(r"долг|кредит|закрывать первым|debt", lower) and "запиш" not in lower:
        return ClassifiedIntent(intent=UserIntent.DEBTS)
    if re.search(r"сколько на|баланс|на картах|на счетах", lower):
        return ClassifiedIntent(intent=UserIntent.BALANCE)
    if re.search(r"расход|отчёт|отчет|report|потратил", lower):
        return ClassifiedIntent(intent=UserIntent.REPORT)
    if re.search(r"зарплат|доход|пришл|income|получил", lower):
        return ClassifiedIntent(intent=UserIntent.INCOME, amount=_extract_amount(lower))
    if re.search(r"купить|позволить|доставк|можем ли", lower) and _extract_amount(lower):
        return ClassifiedIntent(intent=UserIntent.PURCHASE_ADVICE, amount=_extract_amount(lower))

    return ClassifiedIntent(intent=UserIntent.EXPENSE)


def _extract_amount(text: str) -> Optional[Decimal]:
    match = re.search(r"(\d[\d\s]*(?:[.,]\d{1,2})?)", text)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(" ", "").replace(",", "."))
    except Exception:
        return None
