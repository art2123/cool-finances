from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import DebtProductType, InterestCalcMethod
from src.models.credit_terms import CreditTerms


async def get_terms(session: AsyncSession, account_id: int) -> Optional[CreditTerms]:
    result = await session.execute(select(CreditTerms).where(CreditTerms.account_id == account_id))
    return result.scalar_one_or_none()


async def get_terms_map(session: AsyncSession, account_ids: List[int]) -> Dict[int, CreditTerms]:
    if not account_ids:
        return {}
    result = await session.execute(select(CreditTerms).where(CreditTerms.account_id.in_(account_ids)))
    return {t.account_id: t for t in result.scalars().all()}


async def upsert_terms(session: AsyncSession, account_id: int, **kwargs) -> CreditTerms:
    terms = await get_terms(session, account_id)
    if terms:
        for k, v in kwargs.items():
            setattr(terms, k, v)
    else:
        terms = CreditTerms(account_id=account_id, **kwargs)
        session.add(terms)
    await session.flush()
    return terms


def default_calc_method(product_type: DebtProductType) -> InterestCalcMethod:
    mapping = {
        DebtProductType.CREDIT_CARD: InterestCalcMethod.DAILY_BALANCE,
        DebtProductType.OVERDRAFT: InterestCalcMethod.DAILY_BALANCE,
        DebtProductType.CONSUMER_LOAN: InterestCalcMethod.AMORTIZING_LOAN,
        DebtProductType.MORTGAGE: InterestCalcMethod.AMORTIZING_LOAN,
        DebtProductType.PERSONAL_DEBT: InterestCalcMethod.NONE,
    }
    return mapping.get(product_type, InterestCalcMethod.SIMPLE_MONTHLY)
