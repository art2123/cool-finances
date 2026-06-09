from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType, TransactionStatus, TransactionType
from src.models.transaction import Transaction
from src.repositories import account_repo


async def _create_user(session: AsyncSession, telegram_id: int) -> "User":
    from src.models.user import User

    user = User(telegram_id=telegram_id, first_name="Test")
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_update_account_name_and_currency(session: AsyncSession) -> None:
    user = await _create_user(session, 100)
    account = await account_repo.create_account(
        session,
        user_id=user.id,
        name="Card",
        currency="RSD",
        balance=Decimal("1000"),
        account_type=AccountType.DEBIT,
    )
    updated = await account_repo.update_account(session, user.id, account.id, name="Visa", currency="EUR")
    assert updated is not None
    assert updated.name == "Visa"
    assert updated.currency == "EUR"


@pytest.mark.asyncio
async def test_count_for_account_blocks_currency_change(session: AsyncSession) -> None:
    user = await _create_user(session, 100)
    account = await account_repo.create_account(
        session,
        user_id=user.id,
        name="Card",
        currency="RSD",
        balance=Decimal("0"),
        account_type=AccountType.DEBIT,
    )
    session.add(
        Transaction(
            user_id=user.id,
            actor_user_id=user.id,
            account_id=account.id,
            type=TransactionType.EXPENSE,
            status=TransactionStatus.CONFIRMED,
            amount=Decimal("100"),
            currency="RSD",
            transaction_date=date.today(),
        )
    )
    await session.flush()
    assert await account_repo.count_for_account(session, account.id) == 1


@pytest.mark.asyncio
async def test_deactivate_account(session: AsyncSession) -> None:
    user = await _create_user(session, 100)
    account = await account_repo.create_account(
        session,
        user_id=user.id,
        name="Card",
        currency="RSD",
        balance=Decimal("0"),
        account_type=AccountType.DEBIT,
    )
    ok = await account_repo.deactivate_account(session, user.id, account.id)
    assert ok is True
    assert account.is_active is False
    accounts = await account_repo.list_accounts(session, user.id)
    assert accounts == []
