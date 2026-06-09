"""Поддерживаемые валюты счетов и операций."""

CURRENCIES = ("RSD", "EUR", "USD", "RUB", "KZT")

CURRENCY_PATTERNS = {
    "RSD": r"динар|rsd|дин",
    "EUR": r"евро|eur|€|euro",
    "USD": r"долл|usd|\$|dollar",
    "RUB": r"рубл|rub|₽|руб",
    "KZT": r"тенге|kzt|₸|тг",
}

CURRENCY_PROMPT_CHOICES = "|".join(CURRENCIES)
