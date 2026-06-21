from decimal import Decimal, InvalidOperation


def parse_amount(text: str | None) -> Decimal:
    normalized = (text or "").strip().replace(" ", "").replace(",", ".")
    if not normalized:
        raise InvalidOperation("empty amount")
    return Decimal(normalized)
