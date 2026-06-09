from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType, TransactionStatus, TransactionType
from src.models.transaction import Transaction
from src.repositories import account_repo, family_repo, transaction_repo, user_repo
from src.repositories.family_repo import FamilyError


async def _create_user(session: AsyncSession, telegram_id: int, name: str) -> "User":
    from src.models.user import User

    user = User(telegram_id=telegram_id, first_name=name)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_create_invite_success(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    invite = await family_repo.create_invite(session, owner, 200)
    assert invite.invitee_telegram_id == 200
    assert invite.owner_user_id == owner.id


@pytest.mark.asyncio
async def test_create_invite_rejects_user_with_accounts(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    invitee = await _create_user(session, 200, "Invitee")
    await account_repo.create_account(
        session,
        user_id=invitee.id,
        name="Card",
        currency="RSD",
        balance=Decimal("0"),
        account_type=AccountType.DEBIT,
    )

    with pytest.raises(FamilyError, match="счета"):
        await family_repo.create_invite(session, owner, invitee.telegram_id)


@pytest.mark.asyncio
async def test_create_invite_rejects_user_with_transactions(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    invitee = await _create_user(session, 200, "Invitee")
    account = await account_repo.create_account(
        session,
        user_id=invitee.id,
        name="Card",
        currency="RSD",
        balance=Decimal("0"),
        account_type=AccountType.DEBIT,
    )
    session.add(
        Transaction(
            user_id=invitee.id,
            account_id=account.id,
            type=TransactionType.EXPENSE,
            status=TransactionStatus.CONFIRMED,
            amount=Decimal("100"),
            currency="RSD",
            transaction_date=date.today(),
        )
    )
    await session.flush()

    with pytest.raises(FamilyError):
        await family_repo.create_invite(session, owner, invitee.telegram_id)


@pytest.mark.asyncio
async def test_resolve_family_returns_owner_for_dependent(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    dependent = await _create_user(session, 200, "Dependent")
    dependent.family_owner_id = owner.id
    await session.flush()

    resolved = await user_repo.get_or_create_user(session, telegram_id=200)
    assert resolved.id == owner.id


@pytest.mark.asyncio
async def test_resolve_family_false_returns_actor(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    dependent = await _create_user(session, 200, "Dependent")
    dependent.family_owner_id = owner.id
    await session.flush()

    actor = await user_repo.get_or_create_user(session, telegram_id=200, resolve_family=False)
    assert actor.id == dependent.id


@pytest.mark.asyncio
async def test_activate_invite_on_first_login(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    await family_repo.create_invite(session, owner, 200)

    resolved = await user_repo.get_or_create_user(
        session, telegram_id=200, first_name="Dependent"
    )
    actor = await user_repo.get_or_create_user(session, telegram_id=200, resolve_family=False)

    assert resolved.id == owner.id
    assert actor.family_owner_id == owner.id


@pytest.mark.asyncio
async def test_remove_member_clears_family_owner_id(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    dependent = await _create_user(session, 200, "Dependent")
    dependent.family_owner_id = owner.id
    await session.flush()

    removed = await family_repo.remove_member(session, owner, dependent.telegram_id)
    assert removed is True
    assert dependent.family_owner_id is None


@pytest.mark.asyncio
async def test_get_family_telegram_ids(session: AsyncSession) -> None:
    owner = await _create_user(session, 100, "Owner")
    dependent = await _create_user(session, 200, "Dependent")
    dependent.family_owner_id = owner.id
    await session.flush()

    ids = await user_repo.get_family_telegram_ids(session, owner.id)
    assert set(ids) == {100, 200}
