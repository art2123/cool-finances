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
    "📜 История",
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

ACCOUNT_TYPE_TAGS = {
    AccountType.DEBIT: "[дб]",
    AccountType.CREDIT: "[к]",
    AccountType.CASH: "[нал]",
    AccountType.DEBT: "[д]",
    AccountType.SAVINGS: "[нак]",
}

ACCOUNT_TYPE_ICONS = {
    AccountType.DEBIT: "💳",
    AccountType.CREDIT: "🔴",
    AccountType.CASH: "💵",
    AccountType.DEBT: "📉",
    AccountType.SAVINGS: "🐷",
}

ASSET_ACCOUNT_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS})
DEBT_ACCOUNT_TYPES = frozenset({AccountType.CREDIT, AccountType.DEBT})
SPENDABLE_ACCOUNT_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.CREDIT, AccountType.SAVINGS})


def format_account_label(account: Account) -> str:
    icon = ACCOUNT_TYPE_ICONS.get(account.account_type, "•")
    tag = ACCOUNT_TYPE_TAGS.get(account.account_type, "")
    return f"{icon} {tag} {account.name}".strip()


def format_account_button(account: Account) -> str:
    return f"{format_account_label(account)} ({account.balance} {account.currency})"


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
        [InlineKeyboardButton(text=format_account_button(a), callback_data=f"{prefix}:{a.id}")]
        for a in accounts
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def expense_accounts_keyboard(
    accounts: list[Account],
    currency: str | None,
    *,
    show_all: bool = False,
    prefix: str = "pick_account",
) -> InlineKeyboardMarkup:
    spendable = [a for a in accounts if a.account_type in SPENDABLE_ACCOUNT_TYPES]
    if show_all or not currency:
        return accounts_keyboard(spendable, prefix)

    cur = currency.upper()
    matching = [a for a in spendable if a.currency.upper() == cur]
    other = [a for a in spendable if a.currency.upper() != cur]

    rows = [
        [InlineKeyboardButton(text=format_account_button(a), callback_data=f"{prefix}:{a.id}")]
        for a in matching
    ]
    if other or not matching:
        rows.append([InlineKeyboardButton(text="Другой счёт", callback_data=f"{prefix}:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def accounts_hub_keyboard(accounts: list[Account]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for account in accounts:
        row.append(InlineKeyboardButton(text=format_account_label(account), callback_data=f"acct_open:{account.id}"))
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
            [InlineKeyboardButton(text="📜 Операции", callback_data=f"acct_tx_history:{account_id}")],
            [InlineKeyboardButton(text="🗑 Деактивировать", callback_data=f"acct_deactivate:{account_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="acct_back")],
        ]
    )


def categories_keyboard(categories: list[Category], prefix: str = "category") -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for cat in categories:
        label = f"{cat.icon or ''} {cat.name}".strip()
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{cat.slug}"))
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
        ],
        resize_keyboard=True,
    )


def more_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Отчёт"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="🔄 Конвертация"), KeyboardButton(text="📉 Долги")],
            [KeyboardButton(text="📈 Проценты"), KeyboardButton(text="🔮 Прогноз")],
            [KeyboardButton(text="🔔 Напоминания"), KeyboardButton(text="🎯 Цели")],
            [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def transaction_list_keyboard(
    transactions: list,
    *,
    page: int,
    total_count: int,
    page_size: int,
    account_id: int | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=label, callback_data=f"tx_open:{tx.id}")]
        for tx, label in transactions
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"tx_page:{page - 1}:{account_id or ''}",
            )
        )
    if (page + 1) * page_size < total_count:
        nav.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"tx_page:{page + 1}:{account_id or ''}",
            )
        )
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def transaction_edit_keyboard(tx_id: int, tx_type: str, *, foreign_expense: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="📅 Дата", callback_data=f"tx_edit:{tx_id}:date")],
    ]

    if tx_type == "conversion":
        rows.extend(
            [
                [InlineKeyboardButton(text="💰 Сумма списания", callback_data=f"tx_edit:{tx_id}:amount")],
                [InlineKeyboardButton(text="💳 Счёт списания", callback_data=f"tx_edit:{tx_id}:account")],
                [InlineKeyboardButton(text="💰 Сумма зачисления", callback_data=f"tx_edit:{tx_id}:counter_amount")],
                [InlineKeyboardButton(text="💳 Счёт зачисления", callback_data=f"tx_edit:{tx_id}:counter_account")],
            ]
        )
    elif tx_type == "transfer":
        rows.extend(
            [
                [InlineKeyboardButton(text="💰 Сумма", callback_data=f"tx_edit:{tx_id}:amount")],
                [InlineKeyboardButton(text="💳 Счёт откуда", callback_data=f"tx_edit:{tx_id}:account")],
                [InlineKeyboardButton(text="💳 Счёт куда", callback_data=f"tx_edit:{tx_id}:counter_account")],
            ]
        )
    else:
        amount_label = "💰 Сумма покупки" if tx_type == "expense" else "💰 Сумма"
        rows.extend(
            [
                [InlineKeyboardButton(text=amount_label, callback_data=f"tx_edit:{tx_id}:amount")],
                [InlineKeyboardButton(text="💱 Валюта", callback_data=f"tx_edit:{tx_id}:currency")],
                [InlineKeyboardButton(text="💳 Счёт", callback_data=f"tx_edit:{tx_id}:account")],
            ]
        )
        if foreign_expense:
            rows.append(
                [InlineKeyboardButton(text="💳 Списание с карты", callback_data=f"tx_edit:{tx_id}:settlement")]
            )
        if tx_type == "expense":
            rows.append(
                [InlineKeyboardButton(text="🏷 Категория", callback_data=f"tx_edit:{tx_id}:category")]
            )

    rows.extend(
        [
            [InlineKeyboardButton(text="📝 Описание", callback_data=f"tx_edit:{tx_id}:merchant")],
            [InlineKeyboardButton(text="💬 Комментарий", callback_data=f"tx_edit:{tx_id}:description")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="tx_back_list")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
