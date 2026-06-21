from decimal import Decimal

from src.bot.keyboards import format_account_button
from src.domain.enums import AccountType
from src.models.account import Account

def test_format_account_button_truncates_long_labels() -> None:
    account = Account(
        id=1,
        user_id=1,
        name="Очень длинное название счёта для проверки обрезки кнопки",
        currency="RUB",
        balance=Decimal("1234567.89"),
        account_type=AccountType.DEBIT,
    )
    text = format_account_button(account)
    assert len(text) <= 64
    assert text.endswith("RUB)")
