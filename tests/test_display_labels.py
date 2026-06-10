from src.domain.enums import TransactionType, transaction_type_label


def test_transaction_type_label_russian() -> None:
    assert transaction_type_label(TransactionType.EXPENSE) == "расходы"
    assert transaction_type_label(TransactionType.INCOME) == "доходы"
    assert transaction_type_label("expense") == "расходы"
    assert transaction_type_label("income") == "доходы"
