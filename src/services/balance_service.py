from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import ASSET_ACCOUNT_TYPES, DEBT_ACCOUNT_TYPES, format_account_label
from src.domain.currencies import CURRENCIES
from src.domain.enums import AccountType
from src.models.account import Account
from src.repositories import account_repo


def format_money(amount: Decimal, currency: str) -> str:
    normalized = amount.quantize(Decimal("0.01"))
    return f"{normalized:,.2f}".replace(",", " ").replace(".00", "") + f" {currency}"


def format_amount(amount: Decimal) -> str:
    normalized = amount.quantize(Decimal("0.01"))
    return f"{normalized:,.2f}".replace(",", " ").replace(".00", "")


def _currency_order(currencies: set[str] | dict) -> list[str]:
    keys = currencies if isinstance(currencies, set) else currencies.keys()
    known = [c for c in CURRENCIES if c in keys]
    extra = sorted(keys - set(CURRENCIES))
    return known + extra


def _format_account_line(account: Account) -> str:
    return f"  {format_account_label(account)} — {format_amount(account.balance)}"


def format_accounts_grouped(accounts: list[Account], *, show_summary: bool = False) -> str:
    if not accounts:
        return "Счетов пока нет. Нажми ➕ Счёт"

    by_currency: dict[str, list[Account]] = defaultdict(list)
    for account in accounts:
        by_currency[account.currency].append(account)

    lines: list[str] = []

    if show_summary:
        asset_totals: dict[str, Decimal] = defaultdict(Decimal)
        debt_totals: dict[str, Decimal] = defaultdict(Decimal)
        for account in accounts:
            if account.account_type in ASSET_ACCOUNT_TYPES:
                asset_totals[account.currency] += account.balance
            elif account.account_type in DEBT_ACCOUNT_TYPES:
                debt_totals[account.currency] += account.balance

        lines.append("*Итого*")
        if asset_totals:
            free_parts = [format_money(asset_totals[c], c) for c in _currency_order(asset_totals)]
            lines.append("Свободно: " + " · ".join(free_parts))
        if debt_totals:
            debt_parts = [format_money(debt_totals[c], c) for c in _currency_order(debt_totals)]
            lines.append("Долг: " + " · ".join(debt_parts))
        lines.append("")

    for currency in _currency_order(by_currency):
        currency_accounts = by_currency[currency]
        assets = [a for a in currency_accounts if a.account_type in ASSET_ACCOUNT_TYPES]
        debts = [a for a in currency_accounts if a.account_type in DEBT_ACCOUNT_TYPES]
        if not assets and not debts:
            continue

        lines.append(f"*{currency}*")
        if assets:
            lines.append("  _Активы_")
            lines.extend(_format_account_line(a) for a in assets)
        if debts:
            lines.append("  _Долги_")
            lines.extend(_format_account_line(a) for a in debts)
        lines.append("")

    return "\n".join(lines).rstrip()


def format_balance_report(accounts: list[Account]) -> str:
    return format_accounts_grouped(accounts, show_summary=True)


def format_accounts_list(accounts: list[Account]) -> str:
    return format_accounts_grouped(accounts, show_summary=False)


async def get_balances_by_currency(session: AsyncSession, user_id: int) -> dict[str, Decimal]:
    accounts = await account_repo.list_accounts(session, user_id)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for account in accounts:
        if account.account_type in ASSET_ACCOUNT_TYPES:
            totals[account.currency] += account.balance
    return dict(totals)


async def get_debt_totals(session: AsyncSession, user_id: int) -> dict[str, Decimal]:
    accounts = await account_repo.list_accounts(session, user_id)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for account in accounts:
        if account.account_type in DEBT_ACCOUNT_TYPES:
            totals[account.currency] += account.balance
    return dict(totals)


def apply_transaction_to_account(account: Account, tx_type: str, amount: Decimal) -> None:
    if tx_type == "expense":
        if account.account_type in ASSET_ACCOUNT_TYPES:
            account.balance -= amount
        elif account.account_type in DEBT_ACCOUNT_TYPES:
            account.balance += amount
    elif tx_type == "income":
        if account.account_type in ASSET_ACCOUNT_TYPES:
            account.balance += amount
    elif tx_type == "debt_payment":
        if account.account_type in ASSET_ACCOUNT_TYPES:
            account.balance -= amount
        elif account.account_type in DEBT_ACCOUNT_TYPES:
            account.balance -= amount
    elif tx_type == "transfer_out":
        account.balance -= amount
    elif tx_type == "transfer_in":
        account.balance += amount
    elif tx_type == "undo_expense":
        if account.account_type in ASSET_ACCOUNT_TYPES:
            account.balance += amount
        elif account.account_type in DEBT_ACCOUNT_TYPES:
            account.balance -= amount
    elif tx_type == "undo_income":
        if account.account_type in ASSET_ACCOUNT_TYPES:
            account.balance -= amount
