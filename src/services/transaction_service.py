from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType, TransactionStatus, TransactionType
from src.domain.schemas import ExpenseDraft
from src.models.account import Account
from src.repositories import account_repo, category_repo, transaction_repo
from src.services.balance_service import apply_transaction_to_account


async def record_expense(
    session: AsyncSession,
    user_id: int,
    account_id: int,
    amount: Decimal,
    currency: str,
    *,
    category_id: int | None = None,
    merchant: str | None = None,
    description: str | None = None,
    transaction_date: date | None = None,
    source_message_id: int | None = None,
    raw_input: str | None = None,
):
    account = await account_repo.get_account_by_id(session, user_id, account_id)
    if not account:
        raise ValueError("Account not found")

    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        type=TransactionType.EXPENSE,
        status=TransactionStatus.CONFIRMED,
        amount=amount,
        currency=currency.upper(),
        account_id=account_id,
        category_id=category_id,
        merchant=merchant,
        description=description,
        transaction_date=transaction_date or date.today(),
        source_message_id=source_message_id,
        source_type="text",
        raw_input=raw_input,
    )
    apply_transaction_to_account(account, "expense", amount)
    return tx, account


async def record_income(
    session: AsyncSession,
    user_id: int,
    account_id: int,
    amount: Decimal,
    currency: str,
    *,
    description: str | None = None,
    transaction_date: date | None = None,
    source_message_id: int | None = None,
    raw_input: str | None = None,
):
    account = await account_repo.get_account_by_id(session, user_id, account_id)
    if not account:
        raise ValueError("Account not found")

    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        type=TransactionType.INCOME,
        status=TransactionStatus.CONFIRMED,
        amount=amount,
        currency=currency.upper(),
        account_id=account_id,
        description=description,
        transaction_date=transaction_date or date.today(),
        source_message_id=source_message_id,
        source_type="text",
        raw_input=raw_input,
    )
    apply_transaction_to_account(account, "income", amount)
    return tx, account


async def record_transfer(
    session: AsyncSession,
    user_id: int,
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    currency: str,
    *,
    transaction_date: date | None = None,
    description: str | None = None,
):
    from_acc = await account_repo.get_account_by_id(session, user_id, from_account_id)
    to_acc = await account_repo.get_account_by_id(session, user_id, to_account_id)
    if not from_acc or not to_acc:
        raise ValueError("Account not found")
    if from_acc.currency != currency or to_acc.currency != currency:
        raise ValueError("Cross-currency transfer not supported in MVP")

    out_tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        type=TransactionType.TRANSFER,
        status=TransactionStatus.CONFIRMED,
        amount=amount,
        currency=currency.upper(),
        account_id=from_account_id,
        counter_account_id=to_account_id,
        description=description or f"Перевод → {to_acc.name}",
        transaction_date=transaction_date or date.today(),
        source_type="text",
    )
    apply_transaction_to_account(from_acc, "transfer_out", amount)
    apply_transaction_to_account(to_acc, "transfer_in", amount)
    return out_tx, from_acc, to_acc


async def undo_last_transaction(session: AsyncSession, user_id: int):
    last_tx = await transaction_repo.get_last_transaction(session, user_id)
    if not last_tx:
        return None

    account = await account_repo.get_account_by_id(session, user_id, last_tx.account_id)
    if not account:
        raise ValueError("Account not found")

    if last_tx.type == TransactionType.EXPENSE:
        apply_transaction_to_account(account, "undo_expense", last_tx.amount)
    elif last_tx.type == TransactionType.INCOME:
        apply_transaction_to_account(account, "undo_income", last_tx.amount)
    elif last_tx.type == TransactionType.TRANSFER:
        apply_transaction_to_account(account, "transfer_in", last_tx.amount)
        if last_tx.counter_account_id:
            counter = await account_repo.get_account_by_id(session, user_id, last_tx.counter_account_id)
            if counter:
                apply_transaction_to_account(counter, "transfer_out", last_tx.amount)

    reversal = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        type=last_tx.type,
        status=TransactionStatus.CANCELLED,
        amount=last_tx.amount,
        currency=last_tx.currency,
        account_id=last_tx.account_id,
        counter_account_id=last_tx.counter_account_id,
        description=f"Отмена операции #{last_tx.id}",
        transaction_date=date.today(),
        source_type="undo",
    )
    last_tx.reversed_by_id = reversal.id
    last_tx.status = TransactionStatus.CANCELLED
    return last_tx, account


async def resolve_category_id(session: AsyncSession, slug: str | None) -> int | None:
    if not slug:
        return None
    category = await category_repo.get_category_by_slug(session, slug)
    if not category:
        category = await category_repo.get_category_by_slug(session, "other")
    return category.id if category else None


async def pick_default_account(
    session: AsyncSession,
    user_id: int,
    currency: str | None,
    account_name: str | None = None,
) -> Account | None:
    accounts = await account_repo.list_accounts(session, user_id)
    if account_name:
        match = await account_repo.get_account_by_name(session, user_id, account_name)
        if match:
            return match

    spendable = [
        a
        for a in accounts
        if a.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.CREDIT, AccountType.SAVINGS)
    ]
    if currency:
        by_currency = [a for a in spendable if a.currency == currency]
        if len(by_currency) == 1:
            return by_currency[0]
        if by_currency:
            return by_currency[0]
    if len(spendable) == 1:
        return spendable[0]
    return None


def draft_missing_fields(draft: ExpenseDraft, account: Account | None) -> list[str]:
    missing = []
    if not draft.amount:
        missing.append("amount")
    if not draft.currency:
        missing.append("currency")
    if not account:
        missing.append("account")
    if draft.transaction_type == TransactionType.EXPENSE and not draft.category_slug:
        missing.append("category")
    return missing
