"""Встроенный справочник магазинов → категория (slug)."""

from __future__ import annotations

import re

MERCHANT_PATTERNS: dict[str, list[str]] = {
    "food": [
        "lidl", "maxi", "idea", "roda", "univerexport", "tempo", "dis",
        "voli", "mercator", "aman", "kineski", "restoran", "pekara",
        "burek", "mesara", "pijaca", "market", "supermarket", "grocery",
    ],
    "cafe": ["starbucks", "costa", "caffe", "kafana", "bistro"],
    "delivery": ["glovo", "wolt", "donesi", "car go", "cargo"],
    "transport": ["nis", "petrol", "mol", "lukoil", "omv", "parking", "gsp"],
    "clothing": ["dm", "pepco", "reserved", "zara", "hm", "h&m", "nike", "adidas"],
    "health": ["apote", "pharm", "drogerie", "benu", "lilly"],
    "subscriptions": ["netflix", "spotify", "youtube", "apple.com"],
    "telecom": ["mts", "telekom", "a1", "yettel", "vip mobile"],
    "housing": ["infostan", "eps", "jkp"],
}

_SKIP_WORDS = frozenset(
    {"the", "ur", "mesto", "shop", "store", "novi", "sad", "beograd", "big"}
)


def normalize_merchant(merchant: str | None) -> str:
    if not merchant:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", merchant, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().upper()
    return cleaned


def match_builtin_category(merchant: str | None) -> str | None:
    if not merchant:
        return None
    upper = merchant.upper()
    normalized = normalize_merchant(merchant)
    for slug, patterns in MERCHANT_PATTERNS.items():
        for pattern in patterns:
            if pattern.upper() in upper or pattern.upper() in normalized:
                return slug
    return None


def extract_merchant_pattern(merchant: str | None) -> str | None:
    """Извлечь короткий паттерн для CategoryRule (например LIDL из «LIDL 174 NOVI S»)."""
    if not merchant:
        return None
    normalized = normalize_merchant(merchant)
    if not normalized:
        return None

    builtin = match_builtin_category(merchant)
    if builtin:
        for pattern in MERCHANT_PATTERNS[builtin]:
            if pattern.upper() in normalized:
                return pattern.upper()

    tokens = [t for t in normalized.split() if t not in _SKIP_WORDS and not t.isdigit()]
    if not tokens:
        return normalized[:32]
    return tokens[0][:32]
