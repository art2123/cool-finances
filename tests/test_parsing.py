from decimal import Decimal, InvalidOperation

import pytest

from src.bot.parsing import parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5000", Decimal("5000")),
        ("25 000", Decimal("25000")),
        ("25,5", Decimal("25.5")),
        ("  1000.25  ", Decimal("1000.25")),
    ],
)
def test_parse_amount(raw: str, expected: Decimal) -> None:
    assert parse_amount(raw) == expected


def test_parse_amount_rejects_empty() -> None:
    with pytest.raises(InvalidOperation):
        parse_amount("")
