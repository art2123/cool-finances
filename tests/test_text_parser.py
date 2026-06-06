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
