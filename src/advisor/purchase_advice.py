from decimal import Decimal
from typing import List, Optional

from src.domain.enums import AccountType
from src.models.account import Account
from src.models.savings_goal import SavingsGoal
from src.services.balance_service import format_money


def advise_purchase(
    amount: Decimal,
    currency: str,
    accounts: List[Account],
    goals: List[SavingsGoal],
    upcoming_mandatory: Decimal = Decimal("0"),
) -> str:
    free = sum(
        a.balance for a in accounts
        if a.currency == currency
        and a.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS)
        and a.balance > 0
    )
    emergency = next(
        (g.target_amount for g in goals if g.is_emergency_fund and g.currency == currency),
        Decimal("0"),
    )
    available = free - upcoming_mandatory - emergency
    after = available - amount

    lines = [
        f"*Совет о покупке {format_money(amount, currency)}*",
        f"Свободно (без кредиток): {format_money(free, currency)}",
    ]
    if upcoming_mandatory > 0:
        lines.append(f"Ближайшие обязательные: −{format_money(upcoming_mandatory, currency)}")
    if emergency > 0:
        lines.append(f"Подушка (не трогаем): {format_money(emergency, currency)}")
    lines.append(f"Доступно для трат: {format_money(available, currency)}")

    if after >= 0:
        lines.append(f"После покупки останется: {format_money(after, currency)}")
        lines.append("✅ Покупка безопасна")
    else:
        lines.append(f"⚠️ Не хватает {format_money(abs(after), currency)}")
        lines.append("Лучше подождать или уменьшить траты")

    return "\n".join(lines)
