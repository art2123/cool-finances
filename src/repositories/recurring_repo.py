from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.recurring_payment import RecurringPayment


async def list_recurring(session: AsyncSession, user_id: int, active_only: bool = True) -> List[RecurringPayment]:
    q = select(RecurringPayment).where(RecurringPayment.user_id == user_id)
    if active_only:
        q = q.where(RecurringPayment.is_active.is_(True))
    result = await session.execute(q)
    return list(result.scalars().all())


async def create_recurring(session: AsyncSession, **kwargs) -> RecurringPayment:
    item = RecurringPayment(**kwargs)
    session.add(item)
    await session.flush()
    return item
