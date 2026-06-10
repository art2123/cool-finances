from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType, TransactionStatus, TransactionType
from src.domain.schemas import ExpenseDraft
from src.models.account import Account
from src.repositories import account_repo, category_repo, transaction_repo
from src.models.transaction import Transaction
from src.services.balance_service import apply_transaction_to_account

SPENDABLE_ACCOUNT_TYPES = frozenset(
    {AccountType.DEBIT, AccountType.CASH, AccountType.CREDIT, AccountType.SAVINGS}
)


def filter_spendable_accounts(accounts: list[Account]) -> list[Account]:
    return [a for a in accounts if a.account_type in SPENDABLE_ACCOUNT_TYPES]


def account_picker_currency(draft: ExpenseDraft) -> str | None:
    if draft.settlement_amount is not None and draft.settlement_currency:
        return draft.settlement_currency.upper()
    return draft.currency.upper() if draft.currency else None


def _expense_debit_amount(tx: Transaction) -> Decimal:
    return tx.counter_amount or tx.amount


def revert_transaction_balances(
    tx: Transaction,
    account: Account,
    counter_account: Account | None,
) -> None:
    if tx.type == TransactionType.EXPENSE:
        apply_transaction_to_account(account, "undo_expense", _expense_debit_amount(tx))
    elif tx.type == TransactionType.INCOME:
        apply_transaction_to_account(account, "undo_income", tx.amount)
    elif tx.type in (TransactionType.TRANSFER, TransactionType.CONVERSION):
        apply_transaction_to_account(account, "transfer_in", tx.amount)
        if counter_account:
            counter_amount = tx.counter_amount or tx.amount
            apply_transaction_to_account(counter_account, "transfer_out", counter_amount)


def apply_transaction_balances(
    tx: Transaction,
    account: Account,
    counter_account: Account | None,
) -> None:
    if tx.type == TransactionType.EXPENSE:
        apply_transaction_to_account(account, "expense", _expense_debit_amount(tx))
    elif tx.type == TransactionType.INCOME:
        apply_transaction_to_account(account, "income", tx.amount)
    elif tx.type in (TransactionType.TRANSFER, TransactionType.CONVERSION):
        apply_transaction_to_account(account, "transfer_out", tx.amount)
        if counter_account:
            counter_amount = tx.counter_amount or tx.amount
            apply_transaction_to_account(counter_account, "transfer_in", counter_amount)


async def record_expense(
    session: AsyncSession,
    user_id: int,
    account_id: int,
    amount: Decimal,
    currency: str,
    *,
    actor_user_id: int | None = None,
    settlement_amount: Decimal | None = None,
    settlement_currency: str | None = None,
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

    expense_currency = currency.upper()
    account_currency = account.currency.upper()
    foreign_purchase = expense_currency != account_currency

    if foreign_purchase:
        if settlement_amount is None:
            raise ValueError("Settlement amount required for foreign-currency purchase")
        debit_amount = settlement_amount
        debit_currency = (settlement_currency or account_currency).upper()
        if debit_currency != account_currency:
            raise ValueError("Settlement currency must match account currency")
    else:
        debit_amount = amount
        debit_currency = expense_currency

    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        actor_user_id=actor_user_id or user_id,
        type=TransactionType.EXPENSE,
        status=TransactionStatus.CONFIRMED,
        amount=amount,
        currency=expense_currency,
        counter_amount=settlement_amount if foreign_purchase else None,
        counter_currency=debit_currency if foreign_purchase else None,
        account_id=account_id,
        category_id=category_id,
        merchant=merchant,
        description=description,
        transaction_date=transaction_date or date.today(),
        source_message_id=source_message_id,
        source_type="text",
        raw_input=raw_input,
    )
    apply_transaction_to_account(account, "expense", debit_amount)
    return tx, account


async def record_income(
    session: AsyncSession,
    user_id: int,
    account_id: int,
    amount: Decimal,
    currency: str,
    *,
    actor_user_id: int | None = None,
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
        actor_user_id=actor_user_id or user_id,
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


async def record_conversion(
    session: AsyncSession,
    user_id: int,
    from_account_id: int,
    to_account_id: int,
    amount_out: Decimal,
    amount_in: Decimal,
    *,
    actor_user_id: int | None = None,
    transaction_date: date | None = None,
    description: str | None = None,
):
    """Обмен валют / крипта: ушло amount_out с одного счёта, пришло amount_in на другой."""
    from_acc = await account_repo.get_account_by_id(session, user_id, from_account_id)
    to_acc = await account_repo.get_account_by_id(session, user_id, to_account_id)
    if not from_acc or not to_acc:
        raise ValueError("Account not found")
    if from_acc.currency == to_acc.currency:
        raise ValueError("Use transfer for same-currency moves")

    tx = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        actor_user_id=actor_user_id or user_id,
        type=TransactionType.CONVERSION,
        status=TransactionStatus.CONFIRMED,
        amount=amount_out,
        currency=from_acc.currency.upper(),
        counter_amount=amount_in,
        counter_currency=to_acc.currency.upper(),
        account_id=from_account_id,
        counter_account_id=to_account_id,
        description=description or f"Конвертация → {to_acc.name}",
        transaction_date=transaction_date or date.today(),
        source_type="conversion",
    )
    apply_transaction_to_account(from_acc, "transfer_out", amount_out)
    apply_transaction_to_account(to_acc, "transfer_in", amount_in)
    return tx, from_acc, to_acc


async def record_transfer(
    session: AsyncSession,
    user_id: int,
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    currency: str,
    *,
    actor_user_id: int | None = None,
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
        actor_user_id=actor_user_id or user_id,
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


async def update_transaction(
    session: AsyncSession,
    user_id: int,
    tx_id: int,
    *,
    amount: Decimal | None = None,
    currency: str | None = None,
    account_id: int | None = None,
    counter_account_id: int | None = None,
    counter_amount: Decimal | None = None,
    counter_currency: str | None = None,
    transaction_date: date | None = None,
    merchant: str | None = None,
    description: str | None = None,
    category_id: int | None = None,
) -> Transaction:
    tx = await transaction_repo.get_transaction_by_id(session, user_id, tx_id)
    if not tx or tx.status != TransactionStatus.CONFIRMED:
        raise ValueError("Transaction not found or not editable")

    financial_update = any(
        field is not None
        for field in (amount, currency, account_id, counter_account_id, counter_amount, counter_currency)
    )
    if not financial_update:
        if transaction_date is not None:
            tx.transaction_date = transaction_date
        if merchant is not None:
            tx.merchant = merchant or None
        if description is not None:
            tx.description = description or None
        if category_id is not None:
            tx.category_id = category_id
        await session.flush()
        await session.refresh(tx)
        return tx

    target_account_id = account_id or tx.account_id
    target_counter_account_id = counter_account_id if counter_account_id is not None else tx.counter_account_id

    new_account = await account_repo.get_account_by_id(session, user_id, target_account_id)
    if not new_account:
        raise ValueError("Account not found")
    new_counter = None
    if target_counter_account_id is not None:
        new_counter = await account_repo.get_account_by_id(session, user_id, target_counter_account_id)
        if not new_counter:
            raise ValueError("Counter account not found")

    if tx.type == TransactionType.CONVERSION and new_counter and new_account.currency == new_counter.currency:
        raise ValueError("Use transfer for same-currency moves")
    if tx.type == TransactionType.TRANSFER and new_counter and new_account.currency != new_counter.currency:
        raise ValueError("Transfer accounts must share currency")
    if tx.type == TransactionType.EXPENSE and (
        (currency.upper() if currency is not None else tx.currency.upper()) != new_account.currency.upper()
        and (counter_amount is None and tx.counter_amount is None)
    ):
        raise ValueError("Settlement amount required for foreign-currency purchase")

    old_account = await account_repo.get_account_by_id(session, user_id, tx.account_id)
    if not old_account:
        raise ValueError("Account not found")
    old_counter = None
    if tx.counter_account_id:
        old_counter = await account_repo.get_account_by_id(session, user_id, tx.counter_account_id)

    revert_transaction_balances(tx, old_account, old_counter)

    if amount is not None:
        tx.amount = amount
    if currency is not None:
        tx.currency = currency.upper()
    tx.account_id = target_account_id
    tx.counter_account_id = target_counter_account_id
    if counter_amount is not None:
        tx.counter_amount = counter_amount
    if counter_currency is not None:
        tx.counter_currency = counter_currency.upper() if counter_currency else None

    if tx.type == TransactionType.CONVERSION:
        tx.currency = new_account.currency.upper()
        if new_counter:
            tx.counter_currency = new_counter.currency.upper()
    elif tx.type == TransactionType.EXPENSE:
        expense_currency = tx.currency.upper()
        account_currency = new_account.currency.upper()
        if expense_currency != account_currency:
            tx.counter_currency = account_currency
            if tx.counter_amount is None:
                raise ValueError("Settlement amount required for foreign-currency purchase")
        else:
            tx.counter_amount = None
            tx.counter_currency = None
    elif tx.type == TransactionType.TRANSFER:
        tx.currency = new_account.currency.upper()

    apply_transaction_balances(tx, new_account, new_counter)

    if transaction_date is not None:
        tx.transaction_date = transaction_date
    if merchant is not None:
        tx.merchant = merchant or None
    if description is not None:
        tx.description = description or None
    if category_id is not None:
        tx.category_id = category_id

    await session.flush()
    await session.refresh(tx)
    return tx


async def undo_last_transaction(session: AsyncSession, user_id: int):
    last_tx = await transaction_repo.get_last_transaction(session, user_id)
    if not last_tx:
        return None

    account = await account_repo.get_account_by_id(session, user_id, last_tx.account_id)
    if not account:
        raise ValueError("Account not found")

    if last_tx.type == TransactionType.EXPENSE:
        undo_amount = last_tx.counter_amount or last_tx.amount
        apply_transaction_to_account(account, "undo_expense", undo_amount)
    elif last_tx.type == TransactionType.INCOME:
        apply_transaction_to_account(account, "undo_income", last_tx.amount)
    elif last_tx.type in (TransactionType.TRANSFER, TransactionType.CONVERSION):
        apply_transaction_to_account(account, "transfer_in", last_tx.amount)
        if last_tx.counter_account_id:
            counter = await account_repo.get_account_by_id(session, user_id, last_tx.counter_account_id)
            if counter:
                counter_amount = last_tx.counter_amount or last_tx.amount
                apply_transaction_to_account(counter, "transfer_out", counter_amount)

    reversal = await transaction_repo.create_transaction(
        session,
        user_id=user_id,
        actor_user_id=last_tx.actor_user_id or last_tx.user_id,
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
    if account_name:
        return await account_repo.get_account_by_name(session, user_id, account_name)
    return None


def needs_settlement(draft: ExpenseDraft, account: Account | None) -> bool:
    if not account or not draft.currency or not draft.amount:
        return False
    if draft.transaction_type != TransactionType.EXPENSE:
        return False
    return draft.currency.upper() != account.currency.upper() and draft.settlement_amount is None


def draft_missing_fields(
    draft: ExpenseDraft,
    account: Account | None,
    account_id: int | None = None,
) -> list[str]:
    missing = []
    if not draft.amount:
        missing.append("amount")
    if not draft.currency:
        missing.append("currency")
    if not account and not account_id:
        missing.append("account")
    if needs_settlement(draft, account):
        missing.append("settlement")
    if draft.transaction_type == TransactionType.EXPENSE and not draft.category_slug:
        missing.append("category")
    return missing
