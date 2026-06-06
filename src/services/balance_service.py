from collections import defaultdict
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType
from src.models.account import Account
from src.repositories import account_repo


def format_money(amount: Decimal, currency: str) -> str:
    normalized = amount.quantize(Decimal("0.01"))
    return f"{normalized:,.2f}".replace(",", " ").replace(".00", "") + f" {currency}"


async def get_balances_by_currency(session: AsyncSession, user_id: int) -> dict[str, Decimal]:
    accounts = await account_repo.list_accounts(session, user_id)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for account in accounts:
        if account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
            totals[account.currency] += account.balance
    return dict(totals)


async def get_debt_totals(session: AsyncSession, user_id: int) -> dict[str, Decimal]:
    accounts = await account_repo.list_accounts(session, user_id)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for account in accounts:
        if account.account_type in (AccountType.CREDIT, AccountType.DEBT):
            totals[account.currency] += account.balance
    return dict(totals)


def apply_transaction_to_account(account: Account, tx_type: str, amount: Decimal) -> None:
    if tx_type == "expense":
        if account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
            account.balance -= amount
        elif account.account_type in (AccountType.CREDIT, AccountType.DEBT):
            account.balance += amount
    elif tx_type == "income":
        if account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
            account.balance += amount
    elif tx_type == "debt_payment":
        if account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
            account.balance -= amount
        elif account.account_type in (AccountType.CREDIT, AccountType.DEBT):
            account.balance -= amount
    elif tx_type == "transfer_out":
        account.balance -= amount
    elif tx_type == "transfer_in":
        account.balance += amount
    elif tx_type == "undo_expense":
        if account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
            account.balance += amount
        elif account.account_type in (AccountType.CREDIT, AccountType.DEBT):
            account.balance -= amount
    elif tx_type == "undo_income":
        if account.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS):
            account.balance -= amount


def format_accounts_list(accounts: list[Account]) -> str:
    if not accounts:
        return "Счетов пока нет. Добавь: /add_account"
    lines = []
    for acc in accounts:
        type_label = {
            AccountType.DEBIT: "дебет",
            AccountType.CREDIT: "кредитка",
            AccountType.CASH: "наличные",
            AccountType.DEBT: "долг",
            AccountType.SAVINGS: "накопления",
        }[acc.account_type]
        lines.append(f"• {acc.name} ({type_label}): {format_money(acc.balance, acc.currency)}")
    return "\n".join(lines)
