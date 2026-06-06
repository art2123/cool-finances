from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user_reminder import UserReminder


async def create_reminder(session: AsyncSession, **kwargs) -> UserReminder:
    reminder = UserReminder(**kwargs)
    session.add(reminder)
    await session.flush()
    return reminder


async def list_reminders(session: AsyncSession, user_id: int, active_only: bool = True) -> List[UserReminder]:
    q = select(UserReminder).where(UserReminder.user_id == user_id).order_by(UserReminder.next_remind_at)
    if active_only:
        q = q.where(UserReminder.is_active.is_(True))
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_due_reminders(session: AsyncSession, now: datetime) -> List[UserReminder]:
    result = await session.execute(
        select(UserReminder).where(
            UserReminder.is_active.is_(True),
            UserReminder.next_remind_at <= now,
        )
    )
    return list(result.scalars().all())


async def get_reminder(session: AsyncSession, user_id: int, reminder_id: int) -> Optional[UserReminder]:
    result = await session.execute(
        select(UserReminder).where(UserReminder.id == reminder_id, UserReminder.user_id == user_id)
    )
    return result.scalar_one_or_none()
