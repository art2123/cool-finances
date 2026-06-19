from decimal import Decimal

from src.bot.keyboards import expense_accounts_keyboard, format_account_button, format_account_label
from src.domain.enums import AccountType
from src.domain.schemas import ExpenseDraft
from src.models.account import Account
from src.services.transaction_service import account_picker_currency, draft_missing_fields


def _account(account_id: int, name: str, currency: str, account_type: AccountType) -> Account:
    return Account(
        id=account_id,
        user_id=1,
        name=name,
        currency=currency,
        balance=Decimal("1000"),
        account_type=account_type,
    )


def test_account_picker_currency_prefers_settlement_currency() -> None:
    draft = ExpenseDraft(
        amount=Decimal("200"),
        currency="RSD",
        settlement_amount=Decimal("1680"),
        settlement_currency="KZT",
    )

    assert account_picker_currency(draft) == "KZT"


def test_expense_accounts_keyboard_groups_matching_currency() -> None:
    accounts = [
        _account(1, "Visa RSD", "RSD", AccountType.DEBIT),
        _account(2, "Cash RSD", "RSD", AccountType.CASH),
        _account(3, "EUR Card", "EUR", AccountType.DEBIT),
        _account(4, "Debt", "RSD", AccountType.DEBT),
    ]

    keyboard = expense_accounts_keyboard(accounts, "RSD")
    rows = keyboard.inline_keyboard

    assert [button.text for button in rows[0]] == [format_account_button(accounts[0])]
    assert [button.text for button in rows[1]] == [format_account_button(accounts[1])]
    assert rows[2][0].text == "Другой счёт"
    assert rows[2][0].callback_data == "pick_account:all"


def test_format_account_label_includes_icon_and_tag() -> None:
    account = _account(1, "Visa RSD", "RSD", AccountType.DEBIT)
    assert format_account_label(account) == "💳 [дб] Visa RSD"

    credit = _account(2, "Тинькофф", "RUB", AccountType.CREDIT)
    assert format_account_label(credit) == "🔴 [к] Тинькофф"


def test_format_account_button_includes_balance() -> None:
    account = _account(1, "Visa RSD", "RSD", AccountType.DEBIT)
    assert format_account_button(account) == "💳 [дб] Visa RSD (1000 RSD)"


def test_draft_missing_fields_uses_account_id_hint() -> None:
    draft = ExpenseDraft(
        amount=Decimal("200"),
        currency="RSD",
        category_slug="food",
    )
    account = _account(1, "EUR Card", "EUR", AccountType.DEBIT)

    assert draft_missing_fields(draft, None) == ["account"]
    assert draft_missing_fields(draft, account) == ["settlement"]
    assert draft_missing_fields(draft, None, account_id=account.id) == []
