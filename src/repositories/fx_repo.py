from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.fx_rate import FxRate


async def get_rate(
    session: AsyncSession,
    base: str,
    quote: str,
    rate_date: Optional[date] = None,
) -> Optional[Decimal]:
    rate_date = rate_date or date.today()
    result = await session.execute(
        select(FxRate)
        .where(
            FxRate.base_currency == base,
            FxRate.quote_currency == quote,
            FxRate.rate_date <= rate_date,
        )
        .order_by(FxRate.rate_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.rate if row else None


async def set_rate(session: AsyncSession, base: str, quote: str, rate: Decimal, rate_date: Optional[date] = None) -> FxRate:
    rate_date = rate_date or date.today()
    result = await session.execute(
        select(FxRate).where(
            FxRate.base_currency == base,
            FxRate.quote_currency == quote,
            FxRate.rate_date == rate_date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.rate = rate
        return existing
    fx = FxRate(base_currency=base, quote_currency=quote, rate=rate, rate_date=rate_date)
    session.add(fx)
    await session.flush()
    return fx
