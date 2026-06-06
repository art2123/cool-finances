from decimal import Decimal

from src.advisor.interest_calculator import monthly_interest_simple


def test_monthly_interest():
    result = monthly_interest_simple(Decimal("180000"), Decimal("19.9"))
    assert result > Decimal("2000")
    assert result < Decimal("4000")
