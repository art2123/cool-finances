import enum


class AccountType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    CASH = "cash"
    DEBT = "debt"
    SAVINGS = "savings"


class TransactionType(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    CONVERSION = "conversion"
    DEBT_PAYMENT = "debt_payment"
    FX_FEE = "fx_fee"


class TransactionStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class DebtProductType(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    CONSUMER_LOAN = "consumer_loan"
    MORTGAGE = "mortgage"
    OVERDRAFT = "overdraft"
    PERSONAL_DEBT = "personal_debt"


class InterestCalcMethod(str, enum.Enum):
    AMORTIZING_LOAN = "amortizing_loan"
    DAILY_BALANCE = "daily_balance"
    SIMPLE_MONTHLY = "simple_monthly"
    NONE = "none"


class ReminderRecurrence(str, enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class RecurrencePeriod(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class LimitPeriod(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class UserIntent(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"
    BALANCE = "balance"
    REPORT = "report"
    INTEREST = "interest"
    WHAT_IF = "what_if"
    AFFORDABILITY = "affordability"
    SAVINGS_PROJECTION = "savings_projection"
    REMINDER = "reminder"
    TRANSFER = "transfer"
    DEBT_ADVICE = "debt_advice"
    PURCHASE_ADVICE = "purchase_advice"
    FORECAST = "forecast"
    DEBTS = "debts"
    UNKNOWN = "unknown"
