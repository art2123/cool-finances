from __future__ import annotations

import base64
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from src.core.config import get_settings
from src.domain.currencies import CURRENCY_PROMPT_CHOICES
from src.domain.enums import TransactionType
from src.domain.schemas import ExpenseDraft, ImageParseResult

VALID_CATEGORY_SLUGS = frozenset({
    "food", "cafe", "delivery", "transport", "housing", "telecom", "subscriptions",
    "health", "clothing", "travel", "business", "debt_payment", "other",
})

VISION_PROMPT = f"""Extract ALL financial transactions from this image.
Sources may include:
- Serbian bank SMS/push (e.g. ALTABanka: "Placanje DINA karticom", fields iznos/mesto/dana)
- Receipts, bank app screenshots with multiple notifications

Return JSON only:
{{
  "transactions": [
    {{
      "amount": number,
      "currency": "{CURRENCY_PROMPT_CHOICES}",
      "merchant": string,
      "transaction_date": "YYYY-MM-DD" or null,
      "category_slug": one of food,cafe,delivery,transport,housing,telecom,subscriptions,health,clothing,travel,business,debt_payment,other or null,
      "confidence": 0-1
    }}
  ]
}}

Rules:
- Include EVERY separate payment/notification visible.
- merchant = shop/place name (mesto), not bank name.
- Parse Serbian amounts: "14,965.48RSD" -> 14965.48, currency RSD.
- transaction_date from "dana DD.MM.YYYY" if present.
- category_slug: guess category from merchant (LIDL/MAXI=food, etc.).
- If only one transaction, still return array with one element.
"""


def parse_amount_value(raw: str | int | float | None) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    s = str(raw).strip().replace(" ", "")
    if not s:
        return None
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_transaction_date(raw: str | None) -> date | None:
    if not raw:
        return None
    cleaned = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            from datetime import datetime

            return datetime.strptime(cleaned[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_vision_response(content: str) -> ImageParseResult:
    cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(cleaned)
    items = data.get("transactions") or []
    if not items and data.get("amount"):
        items = [data]

    transactions: list[ExpenseDraft] = []
    for item in items:
        amount = parse_amount_value(item.get("amount"))
        if amount is None:
            continue
        currency = (item.get("currency") or "RSD").upper()
        slug = item.get("category_slug")
        if slug and slug not in VALID_CATEGORY_SLUGS:
            slug = None
        transactions.append(
            ExpenseDraft(
                amount=amount,
                currency=currency,
                merchant=item.get("merchant"),
                category_slug=slug,
                transaction_type=TransactionType.EXPENSE,
                transaction_date=parse_transaction_date(item.get("transaction_date")),
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    return ImageParseResult(transactions=transactions, raw_json=cleaned)


async def parse_image_transactions(image_bytes: bytes, *, mime_type: str = "image/jpeg") -> ImageParseResult:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    b64 = base64.b64encode(image_bytes).decode()
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                            },
                        ],
                    }
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    return parse_vision_response(content)
