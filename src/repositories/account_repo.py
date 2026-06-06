from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AccountType
from src.models.account import Account


async def list_accounts(session: AsyncSession, user_id: int, active_only: bool = True) -> list[Account]:
    query = select(Account).where(Account.user_id == user_id).order_by(Account.sort_order, Account.id)
    if active_only:
        query = query.where(Account.is_active.is_(True))
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_account_by_name(session: AsyncSession, user_id: int, name: str) -> Account | None:
    result = await session.execute(
        select(Account).where(Account.user_id == user_id, Account.name.ilike(name))
    )
    return result.scalar_one_or_none()


async def get_account_by_id(session: AsyncSession, user_id: int, account_id: int) -> Account | None:
    result = await session.execute(
        select(Account).where(Account.user_id == user_id, Account.id == account_id)
    )
    return result.scalar_one_or_none()


async def create_account(
    session: AsyncSession,
    user_id: int,
    name: str,
    currency: str,
    balance: Decimal,
    account_type: AccountType,
) -> Account:
    account = Account(
        user_id=user_id,
        name=name,
        currency=currency.upper(),
        balance=balance,
        account_type=account_type,
    )
    session.add(account)
    await session.flush()
    return account
