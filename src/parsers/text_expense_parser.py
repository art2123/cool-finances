from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from src.core.config import get_settings
from src.domain.enums import TransactionType
from src.domain.schemas import ExpenseDraft

CURRENCY_PATTERNS = {
    "RSD": r"динар|rsd|дин",
    "EUR": r"евро|eur|€|euro",
    "USD": r"долл|usd|\$|dollar",
}

CATEGORY_KEYWORDS = {
    "cafe": ["кофе", "кафе", "coffee", "латте", "капучино"],
    "food": ["еда", "продукты", "супермаркет", "молоко", "хлеб", "обед"],
    "delivery": ["доставка", "glovo", "wolt", "борис"],
    "transport": ["такси", "бензин", "автобус", "uber", "bolt"],
    "subscriptions": ["netflix", "spotify", "подписка", "youtube"],
    "housing": ["аренда", "квартира", "коммунал"],
    "telecom": ["интернет", "телефон", "мтс", "телеком"],
}


def _detect_currency(text: str) -> str | None:
    lower = text.lower()
    for currency, pattern in CURRENCY_PATTERNS.items():
        if re.search(pattern, lower):
            return currency
    return None


def _detect_category(text: str) -> str | None:
    lower = text.lower()
    for slug, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return slug
    return None


def _extract_amount(text: str) -> Decimal | None:
    patterns = [
        r"(\d[\d\s]*(?:[.,]\d{1,2})?)\s*(?:динар|rsd|евро|eur|usd|\$|€)?",
        r"(?:на|за)\s+(\d[\d\s]*(?:[.,]\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return Decimal(raw)
            except InvalidOperation:
                continue
    return None


def _is_income(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in ["зарплат", "доход", "пришл", "получил", "income", "фриланс"])


def parse_expense_regex(text: str) -> ExpenseDraft:
    amount = _extract_amount(text)
    currency = _detect_currency(text) or ("RSD" if amount else None)
    category = _detect_category(text)
    tx_type = TransactionType.INCOME if _is_income(text) else TransactionType.EXPENSE

    merchant = None
    if amount:
        cleaned = re.sub(r"\d[\d\s.,]*", "", text, count=1)
        for pattern in CURRENCY_PATTERNS.values():
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        merchant = cleaned.strip(" -–—,.") or None

    return ExpenseDraft(
        amount=amount,
        currency=currency,
        merchant=merchant,
        category_slug=category,
        transaction_type=tx_type,
        transaction_date=date.today(),
        confidence=0.6 if amount else 0.2,
        raw_input=text,
    )


async def parse_expense_text(text: str) -> ExpenseDraft:
    settings = get_settings()
    if not settings.openai_api_key:
        draft = parse_expense_regex(text)
        draft.description = text
        return draft

    prompt = f"""Extract expense from user message. Return JSON only:
{{
  "amount": number or null,
  "currency": "RSD"|"EUR"|"USD" or null,
  "merchant": string or null,
  "category_slug": one of food,cafe,delivery,transport,housing,telecom,subscriptions,health,clothing,travel,business,debt_payment,other or null,
  "transaction_type": "expense"|"income"|"transfer",
  "confidence": 0-1
}}
Message: {text}"""

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(content)

    return ExpenseDraft(
        amount=Decimal(str(data["amount"])) if data.get("amount") else None,
        currency=data.get("currency"),
        merchant=data.get("merchant"),
        category_slug=data.get("category_slug"),
        transaction_type=TransactionType(data.get("transaction_type", "expense")),
        transaction_date=date.today(),
        confidence=float(data.get("confidence", 0.7)),
        description=text,
    )
