from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from src.domain.enums import AccountType
from src.models.account import Account
from src.models.recurring_payment import RecurringPayment
from src.models.savings_goal import SavingsGoal
from src.services.balance_service import format_money


@dataclass
class ForecastResult:
    period_label: str
    expected_income: Decimal
    mandatory_payments: Decimal
    variable_spending: Decimal
    free_after: Decimal
    can_afford: bool
    shortfall: Decimal
    message: str


def _sum_by_currency(items: List[tuple], currency: str) -> Decimal:
    return sum((amt for cur, amt in items if cur == currency), Decimal("0"))


def build_month_forecast(
    accounts: List[Account],
    recurring: List[RecurringPayment],
    goals: List[SavingsGoal],
    avg_monthly_spending: Dict[str, Decimal],
    purchase_amount: Optional[Decimal] = None,
    purchase_currency: str = "RSD",
    hypothetical_spending: Optional[Decimal] = None,
    period_days: int = 30,
) -> ForecastResult:
    today = date.today()
    period_end = today + timedelta(days=period_days)
    period_label = f"{today.strftime('%d.%m')} — {period_end.strftime('%d.%m.%Y')}"

    income_items = []
    expense_items = []
    for r in recurring:
        if not r.is_active:
            continue
        if r.next_date <= period_end:
            if r.is_income:
                income_items.append((r.currency, r.amount))
            elif r.is_mandatory:
                expense_items.append((r.currency, r.amount))

    expected_income = _sum_by_currency(income_items, purchase_currency)
    mandatory = _sum_by_currency(expense_items, purchase_currency)
    variable = hypothetical_spending or avg_monthly_spending.get(purchase_currency, Decimal("0"))

    free_cash = sum(
        a.balance for a in accounts
        if a.currency == purchase_currency
        and a.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS)
    )
    emergency = next(
        (g.target_amount for g in goals if g.is_emergency_fund and g.currency == purchase_currency),
        Decimal("0"),
    )

    free_after = free_cash + expected_income - mandatory - variable
    if purchase_amount:
        free_after -= purchase_amount

    can_afford = free_after >= emergency
    shortfall = max(emergency - free_after, Decimal("0")) if not can_afford else Decimal("0")

    lines = [
        f"*Прогноз на {period_label}* ({purchase_currency})",
        f"Доход: +{expected_income:,.0f}",
        f"Обязательные платежи: −{mandatory:,.0f}",
        f"Переменные траты: −{variable:,.0f}",
    ]
    if purchase_amount:
        lines.append(f"Покупка: −{purchase_amount:,.0f}")
    lines.append(f"Останется: *{free_after:,.0f}*")
    if emergency > 0:
        lines.append(f"Подушка: {emergency:,.0f}")
    if purchase_amount:
        lines.append("✅ Можно позволить" if can_afford else f"⚠️ Не хватает ~{shortfall:,.0f}")
    elif free_after > emergency:
        savings = free_after - emergency
        lines.append(f"Можно отложить: ~{savings:,.0f}")

    return ForecastResult(
        period_label=period_label,
        expected_income=expected_income,
        mandatory_payments=mandatory,
        variable_spending=variable,
        free_after=free_after,
        can_afford=can_afford,
        shortfall=shortfall,
        message="\n".join(lines),
    )
