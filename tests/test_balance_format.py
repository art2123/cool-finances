from decimal import Decimal

from src.domain.enums import AccountType
from src.models.account import Account
from src.services import balance_service


def _account(name: str, currency: str, balance: str, account_type: AccountType, account_id: int) -> Account:
    return Account(
        id=account_id,
        user_id=1,
        name=name,
        currency=currency,
        balance=Decimal(balance),
        account_type=account_type,
    )


def test_format_accounts_grouped_by_currency_and_type() -> None:
    accounts = [
        _account("Kaspi Яна", "RUB", "5724.84", AccountType.DEBIT, 1),
        _account("Тинькофф Яна", "RUB", "-357370.73", AccountType.CREDIT, 2),
        _account("Kaspi Артём", "KZT", "8882.53", AccountType.DEBIT, 3),
    ]
    text = balance_service.format_accounts_grouped(accounts)

    assert "*RUB*" in text
    assert "*KZT*" in text
    assert "_Активы_" in text
    assert "_Долги_" in text
    assert "Kaspi Яна" in text
    assert "Тинькофф Яна" in text
    assert "Kaspi Артём" in text
    assert "[дб]" in text
    assert "[к]" in text
    assert "💳 [дб] Kaspi Яна" in text
    assert "🔴 [к] Тинькофф Яна" in text


def test_format_balance_report_includes_summary() -> None:
    accounts = [
        _account("Kaspi Яна", "RUB", "5724.84", AccountType.DEBIT, 1),
        _account("Тинькофф Яна", "RUB", "-357370.73", AccountType.CREDIT, 2),
    ]
    text = balance_service.format_balance_report(accounts)

    assert "*Итого*" in text
    assert "Свободно:" in text
    assert "5 724.84 RUB" in text
    assert "Долг:" in text
    assert "-357 370.73 RUB" in text


def test_single_currency_without_debts_hides_debts_section() -> None:
    accounts = [_account("Наличные", "EUR", "100", AccountType.CASH, 1)]
    text = balance_service.format_accounts_grouped(accounts)

    assert "_Активы_" in text
    assert "_Долги_" not in text


def test_empty_accounts_list() -> None:
    assert "Счетов пока нет" in balance_service.format_accounts_grouped([])
