import json

import pytest

from src.parsers.image_expense_parser import parse_amount_value, parse_transaction_date, parse_vision_response


ALTABANKA_FIXTURE = {
    "transactions": [
        {
            "amount": 14965.48,
            "currency": "RSD",
            "merchant": "LIDL 174 NOVI S",
            "transaction_date": "2026-06-21",
            "category_slug": "food",
            "confidence": 0.95,
        },
        {
            "amount": 549.98,
            "currency": "RSD",
            "merchant": "LIDL 174 NOVI S",
            "transaction_date": "2026-06-21",
            "category_slug": "food",
            "confidence": 0.95,
        },
        {
            "amount": 1570.00,
            "currency": "RSD",
            "merchant": "UR KINESKI 88>N",
            "transaction_date": "2026-06-21",
            "category_slug": "food",
            "confidence": 0.9,
        },
        {
            "amount": 1532.95,
            "currency": "RSD",
            "merchant": "213 - MAXI 217>",
            "transaction_date": "2026-06-21",
            "category_slug": "food",
            "confidence": 0.92,
        },
        {
            "amount": 10100.00,
            "currency": "RSD",
            "merchant": "Y115 Big Novi S",
            "transaction_date": "2026-06-21",
            "category_slug": "other",
            "confidence": 0.85,
        },
    ]
}


def test_parse_amount_with_thousands_comma():
    assert float(parse_amount_value("14,965.48")) == 14965.48
    assert float(parse_amount_value("1,570.00")) == 1570.00


def test_parse_amount_european_decimal():
    assert float(parse_amount_value("549,98")) == 549.98


def test_parse_transaction_date_iso():
    assert parse_transaction_date("2026-06-21").isoformat() == "2026-06-21"


def test_parse_vision_response_altabanka():
    result = parse_vision_response(json.dumps(ALTABANKA_FIXTURE))
    assert len(result.transactions) == 5
    assert result.transactions[0].merchant == "LIDL 174 NOVI S"
    assert float(result.transactions[0].amount) == 14965.48
    assert result.transactions[0].currency == "RSD"
    assert result.transactions[0].category_slug == "food"


def test_parse_vision_response_single_legacy():
    payload = {
        "amount": 200,
        "currency": "RSD",
        "merchant": "кафе",
        "category_slug": "cafe",
        "confidence": 0.8,
    }
    result = parse_vision_response(json.dumps(payload))
    assert len(result.transactions) == 1
    assert float(result.transactions[0].amount) == 200
