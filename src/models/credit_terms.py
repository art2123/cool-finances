from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.domain.enums import DebtProductType, InterestCalcMethod


class CreditTerms(Base):
    __tablename__ = "credit_terms"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    product_type: Mapped[DebtProductType] = mapped_column(
        Enum(DebtProductType, name="debt_product_type"), nullable=False
    )
    calc_method: Mapped[InterestCalcMethod] = mapped_column(
        Enum(InterestCalcMethod, name="interest_calc_method"), nullable=False
    )
    principal_original: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    interest_rate_annual: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    nominal_annual_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    min_payment: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    payment_day: Mapped[Optional[int]] = mapped_column(SmallInteger)
    next_payment_date: Mapped[Optional[date]] = mapped_column(Date)
    term_months: Mapped[Optional[int]] = mapped_column(Integer)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    target_close_date: Mapped[Optional[date]] = mapped_column(Date)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    grace_period_days: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0)
    min_payment_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    overdraft_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    lender_name: Mapped[Optional[str]] = mapped_column(Text)
    contract_number: Mapped[Optional[str]] = mapped_column(Text)
    terms_confirmed: Mapped[bool] = mapped_column(default=False)
    extracted_raw: Mapped[Optional[dict]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
