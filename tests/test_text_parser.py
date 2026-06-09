from src.parsers.text_expense_parser import parse_expense_regex


def test_parse_coffee_rsd():
    draft = parse_expense_regex("кофе 200 динар")
    assert draft.amount is not None
    assert float(draft.amount) == 200
    assert draft.currency == "RSD"
    assert draft.category_slug == "cafe"


def test_parse_products():
    draft = parse_expense_regex("продукты 3500")
    assert float(draft.amount) == 3500
    assert draft.category_slug == "food"


def test_parse_rub():
    draft = parse_expense_regex("обед 850 рублей")
    assert float(draft.amount) == 850
    assert draft.currency == "RUB"


def test_parse_kzt():
    draft = parse_expense_regex("такси 2500 тенге")
    assert float(draft.amount) == 2500
    assert draft.currency == "KZT"


def test_parse_foreign_card_settlement():
    draft = parse_expense_regex("кофе 200 динар списали 1680 тенге")
    assert float(draft.amount) == 200
    assert draft.currency == "RSD"
    assert float(draft.settlement_amount) == 1680
    assert draft.settlement_currency == "KZT"
