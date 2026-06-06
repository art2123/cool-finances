from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from src.advisor.interest_calculator import estimate_monthly_interest, monthly_interest_simple
from src.domain.enums import AccountType
from src.models.account import Account
from src.models.credit_terms import CreditTerms
from src.services.balance_service import format_money


@dataclass
class WhatIfResult:
    account_name: str
    currency: str
    current_debt: Decimal
    new_debt: Decimal
    current_monthly_interest: Decimal
    new_monthly_interest: Decimal
    interest_saved_monthly: Decimal
    cash_remaining: Decimal
    is_safe: bool
    message: str


def simulate_extra_payment(
    debt_account: Account,
    terms: Optional[CreditTerms],
    payment_amount: Decimal,
    cash_accounts: List[Account],
    emergency_fund: Decimal = Decimal("0"),
) -> WhatIfResult:
    current_debt = debt_account.balance
    new_debt = max(current_debt - payment_amount, Decimal("0"))
    current_int = estimate_monthly_interest(debt_account, terms)

    temp_account = Account(
        id=debt_account.id,
        user_id=debt_account.user_id,
        name=debt_account.name,
        currency=debt_account.currency,
        balance=new_debt,
        account_type=debt_account.account_type,
    )
    new_int = estimate_monthly_interest(temp_account, terms)
    saved = current_int - new_int

    free_cash = sum(
        a.balance for a in cash_accounts
        if a.currency == debt_account.currency
        and a.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS)
    )
    cash_after = free_cash - payment_amount
    is_safe = cash_after >= emergency_fund

    msg_lines = [
        f"*{debt_account.name}* — доплата {format_money(payment_amount, debt_account.currency)}",
        f"Долг: {format_money(current_debt, debt_account.currency)} → {format_money(new_debt, debt_account.currency)}",
        f"Проценты/мес: {current_int:,.0f} → {new_int:,.0f} (экономия ~{saved:,.0f})",
        f"Свободный cash после: {format_money(cash_after, debt_account.currency)}",
    ]
    if emergency_fund > 0:
        msg_lines.append(f"Подушка: {format_money(emergency_fund, debt_account.currency)}")
    msg_lines.append("✅ Безопасно" if is_safe else "⚠️ Ниже подушки безопасности — рискованно")

    return WhatIfResult(
        account_name=debt_account.name,
        currency=debt_account.currency,
        current_debt=current_debt,
        new_debt=new_debt,
        current_monthly_interest=current_int,
        new_monthly_interest=new_int,
        interest_saved_monthly=saved,
        cash_remaining=cash_after,
        is_safe=is_safe,
        message="\n".join(msg_lines),
    )


def compare_payment_targets(
    amount: Decimal,
    targets: List[tuple],
    cash_accounts: List[Account],
) -> str:
    """targets: list of (account, terms)"""
    lines = [f"*Куда выгоднее {amount:,.0f}?*", ""]
    best = None
    best_saved = Decimal("-1")

    for account, terms in targets:
        if not terms or not terms.interest_rate_annual:
            continue
        saved = monthly_interest_simple(account.balance, terms.interest_rate_annual) - monthly_interest_simple(
            max(account.balance - amount, Decimal("0")), terms.interest_rate_annual
        )
        lines.append(f"• {account.name} ({terms.interest_rate_annual}%): экономия ~{saved:,.0f}/мес")
        if saved > best_saved:
            best_saved = saved
            best = account.name

    if best:
        lines.append("")
        lines.append(f"Рекомендация: сначала *{best}* (макс. экономия на процентах)")
    return "\n".join(lines)
