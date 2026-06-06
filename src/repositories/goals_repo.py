from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.savings_goal import SavingsGoal


async def list_goals(session: AsyncSession, user_id: int) -> List[SavingsGoal]:
    result = await session.execute(select(SavingsGoal).where(SavingsGoal.user_id == user_id))
    return list(result.scalars().all())


async def get_emergency_fund(session: AsyncSession, user_id: int, currency: str) -> Optional[SavingsGoal]:
    result = await session.execute(
        select(SavingsGoal).where(
            SavingsGoal.user_id == user_id,
            SavingsGoal.is_emergency_fund.is_(True),
            SavingsGoal.currency == currency,
        )
    )
    return result.scalar_one_or_none()


async def upsert_emergency_fund(session: AsyncSession, user_id: int, amount, currency: str) -> SavingsGoal:
    goal = await get_emergency_fund(session, user_id, currency)
    if goal:
        goal.target_amount = amount
        return goal
    goal = SavingsGoal(
        user_id=user_id,
        name="Подушка безопасности",
        target_amount=amount,
        currency=currency,
        is_emergency_fund=True,
        priority=1,
    )
    session.add(goal)
    await session.flush()
    return goal
