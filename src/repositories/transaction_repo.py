from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import TransactionStatus, TransactionType
from src.models.transaction import Transaction


async def count_for_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
    )
    return result.scalar_one()


async def create_transaction(session: AsyncSession, **kwargs) -> Transaction:
    tx = Transaction(**kwargs)
    session.add(tx)
    await session.flush()
    return tx


async def get_last_transaction(session: AsyncSession, user_id: int) -> Transaction | None:
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.CONFIRMED,
            Transaction.reversed_by_id.is_(None),
        )
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_expenses_sum(
    session: AsyncSession,
    user_id: int,
    since: date,
    until: date | None = None,
) -> dict[str, Decimal]:
    until = until or date.today()
    result = await session.execute(
        select(Transaction.currency, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.status == TransactionStatus.CONFIRMED,
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= until,
        )
        .group_by(Transaction.currency)
    )
    return {row[0]: row[1] for row in result.all()}


async def get_top_categories(
    session: AsyncSession,
    user_id: int,
    since: date,
    limit: int = 5,
) -> list:
    from src.models.category import Category

    result = await session.execute(
        select(Category.name, Category.icon, func.sum(Transaction.amount))
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.status == TransactionStatus.CONFIRMED,
            Transaction.transaction_date >= since,
        )
        .group_by(Category.name, Category.icon)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(limit)
    )
    return list(result.all())


async def get_totals_by_actor(
    session: AsyncSession,
    user_id: int,
    since: date,
    tx_types: list[TransactionType],
    until: date | None = None,
) -> list[tuple[int, str, Decimal]]:
    """Returns (actor_user_id, currency, total_amount) grouped by actor."""
    until = until or date.today()
    actor_id = func.coalesce(Transaction.actor_user_id, Transaction.user_id)
    result = await session.execute(
        select(actor_id, Transaction.currency, func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user_id,
            Transaction.type.in_(tx_types),
            Transaction.status == TransactionStatus.CONFIRMED,
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= until,
        )
        .group_by(actor_id, Transaction.currency)
        .order_by(actor_id, Transaction.currency)
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def get_transfer_stats_by_actor(
    session: AsyncSession,
    user_id: int,
    since: date,
    until: date | None = None,
) -> list[tuple[int, str, int, Decimal]]:
    """Returns (actor_user_id, currency, operation_count, total_amount)."""
    until = until or date.today()
    actor_id = func.coalesce(Transaction.actor_user_id, Transaction.user_id)
    result = await session.execute(
        select(actor_id, Transaction.currency, func.count(), func.sum(Transaction.amount))
        .where(
            Transaction.user_id == user_id,
            Transaction.type.in_([TransactionType.TRANSFER, TransactionType.CONVERSION]),
            Transaction.status == TransactionStatus.CONFIRMED,
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= until,
        )
        .group_by(actor_id, Transaction.currency)
        .order_by(actor_id, Transaction.currency)
    )
    return [(row[0], row[1], row[2], row[3]) for row in result.all()]


def period_start(period: str) -> date:
    today = date.today()
    if period == "day":
        return today
    if period == "week":
        return today - timedelta(days=today.weekday())
    if period == "month":
        return today.replace(day=1)
    raise ValueError(f"Unknown period: {period}")
