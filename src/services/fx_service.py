from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import fx_repo


async def convert(
    session: AsyncSession,
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    rate_date: Optional[date] = None,
) -> Optional[Decimal]:
    if from_currency == to_currency:
        return amount
    rate = await fx_repo.get_rate(session, from_currency, to_currency, rate_date)
    if rate:
        return (amount * rate).quantize(Decimal("0.01"))
    inverse = await fx_repo.get_rate(session, to_currency, from_currency, rate_date)
    if inverse and inverse > 0:
        return (amount / inverse).quantize(Decimal("0.01"))
    return None
