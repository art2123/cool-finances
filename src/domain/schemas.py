from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.domain.enums import AccountType, TransactionType


class ImageParseResult(BaseModel):
    transactions: list["ExpenseDraft"] = Field(default_factory=list)
    raw_json: Optional[str] = None


class ExpenseDraft(BaseModel):
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    settlement_amount: Optional[Decimal] = None
    settlement_currency: Optional[str] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    category_slug: Optional[str] = None
    transaction_type: TransactionType = TransactionType.EXPENSE
    transaction_date: Optional[date] = None
    account_name: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    raw_input: Optional[str] = None


class AccountCreate(BaseModel):
    name: str
    currency: str = "RSD"
    balance: Decimal = Decimal("0")
    account_type: AccountType = AccountType.DEBIT
