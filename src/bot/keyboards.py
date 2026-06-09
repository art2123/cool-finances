from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.domain.currencies import CURRENCIES
from src.domain.enums import AccountType
from src.models.account import Account
from src.models.category import Category

# Главное меню + legacy-кнопки для старых клавиатур
MAIN_MENU_BUTTON_TEXTS = (
    "💰 Баланс",
    "💳 Счета",
    "💸 Перевод",
    "📋 Ещё",
    "↩️ Отмена",
    "⤴️ Отмена",
    # legacy
    "📊 Отчёт",
    "➕ Счёт",
    "🔄 Конвертация",
    "📉 Долги",
    "📈 Проценты",
    "🔮 Прогноз",
    "🔔 Напоминания",
    "🎯 Цели",
    "❓ Помощь",
)

MORE_MENU_BUTTON_TEXTS = (
    "📊 Отчёт",
    "🔄 Конвертация",
    "📉 Долги",
    "📈 Проценты",
    "🔮 Прогноз",
    "🔔 Напоминания",
    "🎯 Цели",
    "❓ Помощь",
    "◀️ Назад",
)

ALL_MENU_BUTTON_TEXTS = MAIN_MENU_BUTTON_TEXTS + MORE_MENU_BUTTON_TEXTS

ACCOUNT_TYPE_LABELS = {
    AccountType.DEBIT: "Дебетовая карта",
    AccountType.CREDIT: "Кредитная карта",
    AccountType.CASH: "Наличные",
    AccountType.DEBT: "Долг",
    AccountType.SAVINGS: "Накопления",
}

ACCOUNT_TYPE_SHORT = {
    AccountType.DEBIT: "дебет",
    AccountType.CREDIT: "кредитка",
    AccountType.CASH: "наличные",
    AccountType.DEBT: "долг",
    AccountType.SAVINGS: "накопления",
}

ACCOUNT_TYPE_ICONS = {
    AccountType.DEBIT: "💳",
    AccountType.CREDIT: "💳",
    AccountType.CASH: "💵",
    AccountType.DEBT: "📉",
    AccountType.SAVINGS: "🐷",
}

ASSET_ACCOUNT_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS})
DEBT_ACCOUNT_TYPES = frozenset({AccountType.CREDIT, AccountType.DEBT})


def currency_keyboard(callback_prefix: str = "currency") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for code in CURRENCIES:
        row.append(InlineKeyboardButton(text=code, callback_data=f"{callback_prefix}:{code}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_type_keyboard(callback_prefix: str = "acct_type") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"{callback_prefix}:{t.value}")]
            for t, label in ACCOUNT_TYPE_LABELS.items()
        ]
    )


def accounts_keyboard(accounts: list[Account], prefix: str = "pick_account") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{a.name} ({a.balance} {a.currency})", callback_data=f"{prefix}:{a.id}")]
        for a in accounts
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def accounts_hub_keyboard(accounts: list[Account]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for account in accounts:
        row.append(InlineKeyboardButton(text=account.name, callback_data=f"acct_open:{account.id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="➕ Добавить счёт", callback_data="acct_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_edit_keyboard(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Название", callback_data=f"acct_edit_name:{account_id}"),
                InlineKeyboardButton(text="💱 Валюта", callback_data=f"acct_edit_currency:{account_id}"),
            ],
            [
                InlineKeyboardButton(text="💰 Баланс", callback_data=f"acct_edit_balance:{account_id}"),
                InlineKeyboardButton(text="🏷 Тип", callback_data=f"acct_edit_type:{account_id}"),
            ],
            [InlineKeyboardButton(text="🗑 Деактивировать", callback_data=f"acct_deactivate:{account_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="acct_back")],
        ]
    )


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
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="💳 Счета")],
            [KeyboardButton(text="💸 Перевод"), KeyboardButton(text="📋 Ещё")],
            [KeyboardButton(text="↩️ Отмена")],
        ],
        resize_keyboard=True,
    )


def more_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Отчёт"), KeyboardButton(text="🔄 Конвертация")],
            [KeyboardButton(text="📉 Долги"), KeyboardButton(text="📈 Проценты")],
            [KeyboardButton(text="🔮 Прогноз"), KeyboardButton(text="🔔 Напоминания")],
            [KeyboardButton(text="🎯 Цели"), KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )
