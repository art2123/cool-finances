from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.domain.enums import RecurrencePeriod


class RecurringPayment(Base):
    __tablename__ = "recurring_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[RecurrencePeriod] = mapped_column(Enum(RecurrencePeriod, name="recurrence_period"), nullable=False)
    next_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
