from decimal import Decimal
from typing import Dict, List, Optional

from src.domain.enums import AccountType, InterestCalcMethod
from src.models.account import Account
from src.models.credit_terms import CreditTerms


def monthly_interest_simple(balance: Decimal, annual_rate: Decimal) -> Decimal:
    if balance <= 0 or annual_rate <= 0:
        return Decimal("0")
    return (balance * annual_rate / Decimal("100") / Decimal("12")).quantize(Decimal("0.01"))


def monthly_interest_daily_balance(balance: Decimal, annual_rate: Decimal) -> Decimal:
    return monthly_interest_simple(balance, annual_rate)


def estimate_monthly_interest(account: Account, terms: Optional[CreditTerms]) -> Decimal:
    balance = account.balance
    if account.account_type == AccountType.DEBIT and balance < 0:
        balance = abs(balance)
    elif account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
        return Decimal("0")

    if not terms or not terms.interest_rate_annual:
        return Decimal("0")

    method = terms.calc_method
    if method == InterestCalcMethod.NONE:
        return Decimal("0")
    if method == InterestCalcMethod.AMORTIZING_LOAN:
        return monthly_interest_simple(balance, terms.interest_rate_annual)
    return monthly_interest_daily_balance(balance, terms.interest_rate_annual)


def build_interest_report(
    accounts: List[Account],
    terms_map: Dict[int, CreditTerms],
) -> str:
    lines = ["*Сколько теряю на процентах:*", ""]
    total_by_currency: Dict[str, Decimal] = {}

    for account in accounts:
        if account.account_type not in (AccountType.CREDIT, AccountType.DEBT):
            if account.account_type == AccountType.DEBIT and account.balance < 0:
                pass
            else:
                continue
        terms = terms_map.get(account.id)
        monthly = estimate_monthly_interest(account, terms)
        if monthly <= 0 and account.balance <= 0:
            continue
        yearly = (monthly * 12).quantize(Decimal("0.01"))
        lines.append(f"• {account.name}: {monthly:,.0f} {account.currency}/мес ({yearly:,.0f}/год)")
        total_by_currency[account.currency] = total_by_currency.get(account.currency, Decimal("0")) + monthly

    if not total_by_currency:
        return "Проценты не начисляются — нет долгов с указанной ставкой.\nДобавь условия: /credit_terms"

    lines.append("")
    lines.append("*ИТОГО:*")
    for cur, total in total_by_currency.items():
        lines.append(f"  {total:,.0f} {cur}/мес ({(total * 12):,.0f}/год)")

    return "\n".join(lines)
