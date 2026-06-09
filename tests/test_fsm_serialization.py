import json
from decimal import Decimal


def test_fsm_state_values_must_be_json_serializable() -> None:
    """Redis FSM storage rejects Decimal and other non-JSON types."""
    balance = Decimal("30000")
    payload = {"name": "Долг Свете", "currency": "RUB", "balance": str(balance)}
    json.dumps(payload)

    with __import__("pytest").raises(TypeError):
        json.dumps({"balance": balance})
