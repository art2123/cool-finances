from decimal import Decimal

from src.bot.handlers.expenses import _draft_foreign_expense, format_draft_preview
from src.bot.keyboards import draft_confirm_keyboard
from src.domain.enums import AccountType, TransactionType
from src.models.account import Account


def _account(account_id: int, name: str, currency: str, account_type: AccountType) -> Account:
    return Account(
        id=account_id,
        user_id=1,
        name=name,
        currency=currency,
        balance=Decimal("1000"),
        account_type=account_type,
    )


def test_draft_confirm_keyboard_expense_has_edit_buttons() -> None:
    draft = {"transaction_type": "expense", "amount": "200", "currency": "RSD", "category_slug": "food"}
    keyboard = draft_confirm_keyboard(draft, foreign_expense=False)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert "💰 Сумма покупки" in labels
    assert "💱 Валюта" in labels
    assert "💳 Счёт" in labels
    assert "🏷 Категория" in labels
    assert "📝 Описание" in labels
    assert "💬 Комментарий" in labels
    assert "📅 Дата" in labels
    assert "✅ Сохранить" in labels
    assert "❌ Отмена" in labels
    assert "💳 Списание с карты" not in labels


def test_draft_confirm_keyboard_foreign_expense_shows_settlement() -> None:
    draft = {
        "transaction_type": "expense",
        "amount": "200",
        "currency": "RSD",
        "settlement_amount": "1680",
        "settlement_currency": "KZT",
    }
    keyboard = draft_confirm_keyboard(draft, foreign_expense=True)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert "💳 Списание с карты" in labels


def test_draft_confirm_keyboard_income_hides_expense_fields() -> None:
    draft = {"transaction_type": "income", "amount": "50000", "currency": "RUB"}
    keyboard = draft_confirm_keyboard(draft)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert "💰 Сумма" in labels
    assert "🏷 Категория" not in labels
    assert "💳 Списание с карты" not in labels


def test_draft_foreign_expense_detects_currency_mismatch() -> None:
    draft = {"transaction_type": TransactionType.EXPENSE, "currency": "RSD", "amount": "200"}
    account = _account(1, "KZT Card", "KZT", AccountType.DEBIT)

    assert _draft_foreign_expense(draft, account) is True


def test_format_draft_preview_shows_comment_and_date() -> None:
    draft = {
        "transaction_type": "expense",
        "amount": "200",
        "currency": "RSD",
        "merchant": "кофе",
        "category_slug": "cafe",
        "description": "утро",
        "transaction_date": "2026-06-10",
    }
    text = format_draft_preview(draft, account_name="Visa RSD")

    assert "Комментарий: утро" in text
    assert "Дата: 2026-06-10" in text
    assert "Место: кофе" in text
    assert "Счёт: Visa RSD" in text
