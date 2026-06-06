from src.domain.enums import UserIntent
from src.parsers.intent_classifier import classify_intent


def test_what_if_intent():
    r = classify_intent("что будет если 50000 закину на visa")
    assert r.intent == UserIntent.WHAT_IF


def test_affordability():
    r = classify_intent("могу ли iPhone за 120000 в следующем месяце")
    assert r.intent == UserIntent.AFFORDABILITY


def test_reminder():
    r = classify_intent("напомни за 5 дней до 25-го про аренду")
    assert r.intent == UserIntent.REMINDER


def test_expense_default():
    r = classify_intent("кофе 200 динар")
    assert r.intent == UserIntent.EXPENSE
