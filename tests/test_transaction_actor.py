from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType, TransactionType
from src.repositories import account_repo, transaction_repo, user_repo
from src.services.transaction_service import record_expense


async def _create_user(session: AsyncSession, telegram_id: int, name: str) -> "User":
    from src.models.user import User

    user = User(telegram_id=telegram_id, first_name=name)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_record_expense_stores_actor(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    actor = await _create_user(session, 200, "Actor")
    account = await account_repo.create_account(
        session,
        user_id=owner.id,
        name="Card",
        currency="RSD",
        balance=Decimal("10000"),
        account_type=AccountType.DEBIT,
    )
    tx, _ = await record_expense(
        session,
        owner.id,
        account.id,
        Decimal("500"),
        "RSD",
        actor_user_id=actor.id,
    )
    assert tx.user_id == owner.id
    assert tx.actor_user_id == actor.id


@pytest.mark.asyncio
async def test_get_totals_by_actor_groups_expenses(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    ivan = await _create_user(session, 200, "Ivan")
    maria = await _create_user(session, 300, "Maria")
    account = await account_repo.create_account(
        session,
        user_id=owner.id,
        name="Card",
        currency="RSD",
        balance=Decimal("100000"),
        account_type=AccountType.DEBIT,
    )
    await record_expense(session, owner.id, account.id, Decimal("300"), "RSD", actor_user_id=ivan.id)
    await record_expense(session, owner.id, account.id, Decimal("200"), "RSD", actor_user_id=maria.id)

    since = date.today()
    rows = await transaction_repo.get_totals_by_actor(
        session, owner.id, since, [TransactionType.EXPENSE]
    )
    by_actor = {actor_id: amount for actor_id, _, amount in rows}
    assert by_actor[ivan.id] == Decimal("300")
    assert by_actor[maria.id] == Decimal("200")


@pytest.mark.asyncio
async def test_format_user_display_name(session: AsyncSession) -> None:
    user = await _create_user(session, 100, "Ivan")
    assert user_repo.format_user_display_name(user) == "Ivan"
    assert user_repo.format_user_display_name(None) == "Без автора"
