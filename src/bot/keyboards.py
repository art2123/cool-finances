from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.domain.enums import AccountType
from src.models.account import Account
from src.models.category import Category

CURRENCIES = ["RSD", "EUR", "USD"]

ACCOUNT_TYPE_LABELS = {
    AccountType.DEBIT: "Дебетовая карта",
    AccountType.CREDIT: "Кредитная карта",
    AccountType.CASH: "Наличные",
    AccountType.DEBT: "Долг",
    AccountType.SAVINGS: "Накопления",
}


def currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"currency:{c}")] for c in CURRENCIES]
    )


def account_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"acct_type:{t.value}")]
            for t, label in ACCOUNT_TYPE_LABELS.items()
        ]
    )


def accounts_keyboard(accounts: list[Account], prefix: str = "pick_account") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{a.name} ({a.balance} {a.currency})", callback_data=f"{prefix}:{a.id}")]
        for a in accounts
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for cat in categories:
        label = f"{cat.icon or ''} {cat.name}".strip()
        row.append(InlineKeyboardButton(text=label, callback_data=f"category:{cat.slug}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="draft:save"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="draft:cancel"),
            ]
        ]
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="📊 Отчёт")],
            [KeyboardButton(text="💳 Счета"), KeyboardButton(text="↩️ Отмена")],
        ],
        resize_keyboard=True,
    )
