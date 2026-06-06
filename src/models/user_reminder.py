from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Numeric, SmallInteger, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.domain.enums import ReminderRecurrence


class UserReminder(Base):
    __tablename__ = "user_reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[Optional[str]] = mapped_column(Text)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"))
    recurrence: Mapped[ReminderRecurrence] = mapped_column(
        Enum(ReminderRecurrence, name="reminder_recurrence"), nullable=False
    )
    day_of_month: Mapped[Optional[int]] = mapped_column(SmallInteger)
    day_of_week: Mapped[Optional[int]] = mapped_column(SmallInteger)
    month_of_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    specific_date: Mapped[Optional[date]] = mapped_column(Date)
    remind_days_before: Mapped[int] = mapped_column(SmallInteger, default=3)
    remind_at_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    timezone: Mapped[str] = mapped_column(Text, default="Europe/Belgrade")
    linked_recurring_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
