from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.advisor import handle_classified_intent
from src.bot.handlers.goals import handle_emergency_fund_text
from src.bot.handlers.reminders import handle_reminder_intent
from src.bot.keyboards import (
    ALL_MENU_BUTTON_TEXTS,
    categories_keyboard,
    draft_confirm_keyboard,
    expense_accounts_keyboard,
    currency_keyboard,
)
from src.bot.states import ExpenseStates
from src.domain.enums import TransactionType, UserIntent, transaction_type_label
from src.parsers.intent_classifier import classify_intent
from src.parsers.text_expense_parser import parse_expense_text
from src.repositories import account_repo, category_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import (
    account_picker_currency,
    filter_spendable_accounts,
    draft_missing_fields,
    record_expense,
    record_income,
    resolve_category_id,
)
from src.domain.schemas import ExpenseDraft

router = Router()


def format_draft_preview(draft: dict, account_name: str = None) -> str:
    tx_type = draft.get("transaction_type", "expense")
    is_income = tx_type == TransactionType.INCOME or tx_type == "income"
    lines = ["*Черновик операции:*"]
    lines.append(f"Тип: {transaction_type_label(tx_type)}")
    if draft.get("transaction_date"):
        if isinstance(draft["transaction_date"], str):
            lines.append(f"Дата: {draft['transaction_date']}")
        else:
            lines.append(f"Дата: {draft['transaction_date'].strftime('%d.%m.%Y')}")
    if draft.get("amount"):
        amount_label = "Сумма" if is_income else "Покупка"
        lines.append(f"{amount_label}: {draft['amount']} {draft.get('currency', '?')}")
    if draft.get("settlement_amount"):
        cur = draft.get("settlement_currency") or "?"
        lines.append(f"Списание с карты: {draft['settlement_amount']} {cur}")
    if draft.get("merchant"):
        lines.append(f"Место: {draft['merchant']}")
    if draft.get("category_slug"):
        lines.append(f"Категория: {draft['category_slug']}")
    if account_name:
        lines.append(f"Счёт: {account_name}")
    if draft.get("description"):
        lines.append(f"Комментарий: {draft['description']}")
    return "\n".join(lines)


def _parse_date_input(text: str) -> date:
    cleaned = text.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d.%m"):
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            if fmt == "%d.%m":
                parsed = parsed.replace(year=date.today().year)
            return parsed
        except ValueError:
            continue
    raise ValueError("Неверный формат даты. Пример: 10.06.2026")


def _draft_foreign_expense(draft: dict, account) -> bool:
    tx_type = draft.get("transaction_type", "expense")
    if tx_type in ("income", TransactionType.INCOME):
        return False
    if draft.get("settlement_amount"):
        return True
    if account and draft.get("currency"):
        return draft["currency"].upper() != account.currency.upper()
    return False


async def _show_draft_confirm(
    message: Message,
    state: FSMContext,
    draft_data: dict,
    *,
    account=None,
) -> None:
    account_name = draft_data.get("account_name")
    if account:
        account_name = account.name
    await state.set_state(ExpenseStates.confirm)
    await message.answer(
        format_draft_preview(draft_data, account_name),
        reply_markup=draft_confirm_keyboard(draft_data, foreign_expense=_draft_foreign_expense(draft_data, account)),
        parse_mode="Markdown",
    )


async def _prompt_account_selection(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    draft: ExpenseDraft,
    user_id: int,
    *,
    show_all: bool = False,
) -> None:
    accounts = await account_repo.list_accounts(session, user_id)
    spendable = filter_spendable_accounts(accounts)
    picker_currency = account_picker_currency(draft)
    if picker_currency and not show_all:
        keyboard = expense_accounts_keyboard(accounts, picker_currency)
    else:
        filtered = spendable
        if picker_currency and show_all:
            filtered = [a for a in spendable if a.currency.upper() != picker_currency.upper()]
            if not filtered:
                filtered = spendable
        keyboard = expense_accounts_keyboard(filtered, None, show_all=True)

    await state.set_state(ExpenseStates.waiting_account)
    if draft.transaction_type == TransactionType.INCOME:
        prompt = "На какой счёт зачислить?"
    else:
        prompt = "С какого счёта списать?"
        if picker_currency:
            prompt += f" (валюта: {picker_currency})"
    await message.answer(prompt, reply_markup=keyboard)


async def start_expense_flow(message: Message, state: FSMContext, session: AsyncSession, text: str) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    await category_repo.ensure_system_categories(session)

    draft = await parse_expense_text(text)

    payload = draft.model_dump(mode="json")
    await state.update_data(draft=payload, telegram_id=message.from_user.id)
    missing = draft_missing_fields(draft, None, account_id=payload.get("account_id"))

    if "amount" in missing:
        await state.set_state(ExpenseStates.waiting_amount)
        await message.answer("Какая сумма?")
        return
    if "currency" in missing:
        await state.set_state(ExpenseStates.waiting_currency)
        await message.answer("В какой валюте?", reply_markup=currency_keyboard())
        return
    if "account" in missing:
        await _prompt_account_selection(message, state, session, draft, user.id)
        return
    account = None
    if payload.get("account_id"):
        account = await account_repo.get_account_by_id(session, user.id, payload["account_id"])
    if "settlement" in missing and account:
        await state.set_state(ExpenseStates.waiting_settlement)
        await message.answer(
            f"Покупка в {draft.currency}, карта {account.currency}.\n"
            f"Сколько списалось с карты? (в {account.currency})"
        )
        return
    if "category" in missing and draft.transaction_type == TransactionType.EXPENSE:
        categories = await category_repo.list_categories(session)
        await state.set_state(ExpenseStates.waiting_category)
        await message.answer("Выбери категорию:", reply_markup=categories_keyboard(categories))
        return

    await _show_draft_confirm(message, state, payload, account=account)


@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_(ALL_MENU_BUTTON_TEXTS))
async def handle_free_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    current = await state.get_state()
    if current:
        return

    if await handle_emergency_fund_text(message, session):
        return
    if await handle_reminder_intent(message, session):
        return

    classified = classify_intent(message.text or "")
    if classified.intent not in (UserIntent.EXPENSE, UserIntent.INCOME, UserIntent.UNKNOWN):
        if await handle_classified_intent(message, session, classified):
            return

    if classified.intent == UserIntent.INCOME:
        text = message.text
        if "зарплат" not in text.lower() and "доход" not in text.lower():
            text = f"доход {text}"
        await start_expense_flow(message, state, session, text)
        return

    await start_expense_flow(message, state, session, message.text)


@router.message(ExpenseStates.waiting_amount)
async def process_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 200")
        return
    data = await state.get_data()
    draft = data["draft"]
    draft["amount"] = str(amount)
    await state.update_data(draft=draft)
    await _continue_draft(message, state, session)


@router.callback_query(ExpenseStates.waiting_currency, F.data.startswith("currency:"))
async def process_draft_currency(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    currency = callback.data.split(":")[1]
    data = await state.get_data()
    draft = data["draft"]
    draft["currency"] = currency
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    account = None
    if draft.get("account_id"):
        account = await account_repo.get_account_by_id(session, user.id, draft["account_id"])
    if account and account.currency.upper() == currency.upper():
        draft.pop("settlement_amount", None)
        draft.pop("settlement_currency", None)
    await state.update_data(draft=draft)
    await callback.message.edit_text(f"Валюта: {currency}")
    await callback.answer()
    await _continue_draft(callback.message, state, session)


@router.callback_query(ExpenseStates.waiting_account, F.data.startswith("pick_account:"))
async def process_draft_account(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    data = await state.get_data()
    draft = data["draft"]
    if callback.data.endswith(":all"):
        await callback.answer()
        await _prompt_account_selection(callback.message, state, session, ExpenseDraft.model_validate(draft), user.id, show_all=True)
        return

    account_id = int(callback.data.split(":")[1])
    account = await account_repo.get_account_by_id(session, user.id, account_id)
    if not account:
        await callback.answer("Счёт не найден", show_alert=True)
        return
    draft["account_id"] = account_id
    draft["account_name"] = account.name
    await state.update_data(draft=draft)
    await callback.message.edit_text(f"Счёт: {account.name}")
    await callback.answer()
    await _continue_draft(callback.message, state, session)


@router.message(ExpenseStates.waiting_settlement)
async def process_settlement(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число — сколько списалось с карты")
        return
    data = await state.get_data()
    draft = data["draft"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    account = await account_repo.get_account_by_id(session, user.id, draft["account_id"])
    draft["settlement_amount"] = str(amount)
    draft["settlement_currency"] = account.currency if account else draft.get("settlement_currency")
    await state.update_data(draft=draft)
    await _continue_draft(message, state, session)


@router.callback_query(ExpenseStates.waiting_category, F.data.startswith("category:"))
async def process_draft_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    slug = callback.data.split(":")[1]
    data = await state.get_data()
    draft = data["draft"]
    draft["category_slug"] = slug
    await state.update_data(draft=draft)
    await callback.message.edit_text(f"Категория: {slug}")
    await callback.answer()
    await _continue_draft(callback.message, state, session)


async def _continue_draft(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    telegram_id = data.get("telegram_id", message.from_user.id if message.from_user else message.chat.id)
    user = await user_repo.get_or_create_user(session, telegram_id=telegram_id)
    draft_data = data["draft"]
    draft = ExpenseDraft.model_validate(draft_data)

    account = None
    account_id = draft_data.get("account_id")
    if account_id:
        account = await account_repo.get_account_by_id(session, user.id, account_id)

    missing = draft_missing_fields(draft, account, account_id=account_id)
    if "currency" in missing:
        await state.set_state(ExpenseStates.waiting_currency)
        await message.answer("В какой валюте?", reply_markup=currency_keyboard())
        return
    if "account" in missing:
        await _prompt_account_selection(message, state, session, draft, user.id)
        return
    if "settlement" in missing and account:
        await state.set_state(ExpenseStates.waiting_settlement)
        await message.answer(
            f"Покупка в {draft.currency}, карта {account.currency}.\n"
            f"Сколько списалось с карты? (в {account.currency})"
        )
        return
    if "category" in missing and draft.transaction_type == TransactionType.EXPENSE:
        categories = await category_repo.list_categories(session)
        await state.set_state(ExpenseStates.waiting_category)
        await message.answer("Выбери категорию:", reply_markup=categories_keyboard(categories))
        return

    if account:
        draft_data["account_id"] = account.id
        draft_data["account_name"] = account.name
        await state.update_data(draft=draft_data)

    await _show_draft_confirm(message, state, draft_data, account=account)


@router.callback_query(ExpenseStates.confirm, F.data.startswith("draft:edit:"))
async def draft_edit_field(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    field = callback.data.split(":")[2]
    data = await state.get_data()
    draft = data["draft"]
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    expense_draft = ExpenseDraft.model_validate(draft)

    if field == "amount":
        await state.set_state(ExpenseStates.waiting_amount)
        await callback.message.answer("Новая сумма?")
    elif field == "currency":
        await state.set_state(ExpenseStates.waiting_currency)
        await callback.message.answer("Выбери валюту:", reply_markup=currency_keyboard())
    elif field == "account":
        await _prompt_account_selection(callback.message, state, session, expense_draft, user.id)
    elif field == "settlement":
        await state.set_state(ExpenseStates.waiting_settlement)
        await callback.message.answer("Сколько списалось с карты?")
    elif field == "category":
        categories = await category_repo.list_categories(session)
        await state.set_state(ExpenseStates.waiting_category)
        await callback.message.answer("Выбери категорию:", reply_markup=categories_keyboard(categories))
    elif field == "merchant":
        await state.set_state(ExpenseStates.waiting_merchant)
        current = draft.get("merchant") or "—"
        await callback.message.answer(f"Текущее описание: {current}\n\nВведи новое (или «-» чтобы очистить):")
    elif field == "description":
        await state.set_state(ExpenseStates.waiting_description)
        current = draft.get("description") or "—"
        await callback.message.answer(f"Текущий комментарий: {current}\n\nВведи новый (или «-» чтобы очистить):")
    elif field == "date":
        await state.set_state(ExpenseStates.waiting_date)
        current = draft.get("transaction_date") or date.today().strftime("%d.%m.%Y")
        await callback.message.answer(f"Текущая дата: {current}\n\nНовая дата? Формат: 10.06.2026")
    await callback.answer()


@router.message(ExpenseStates.waiting_merchant)
async def process_draft_merchant(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    merchant = None if text in {"-", "—", ""} else text
    data = await state.get_data()
    draft = data["draft"]
    draft["merchant"] = merchant
    await state.update_data(draft=draft)
    await _continue_draft(message, state, session)


@router.message(ExpenseStates.waiting_description)
async def process_draft_description(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    description = None if text in {"-", "—", ""} else text
    data = await state.get_data()
    draft = data["draft"]
    draft["description"] = description
    await state.update_data(draft=draft)
    await _continue_draft(message, state, session)


@router.message(ExpenseStates.waiting_date)
async def process_draft_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        new_date = _parse_date_input(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    draft = data["draft"]
    draft["transaction_date"] = new_date.isoformat()
    await state.update_data(draft=draft)
    await _continue_draft(message, state, session)


@router.callback_query(ExpenseStates.confirm, F.data == "draft:save")
async def save_draft(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, actor = await user_repo.resolve_data_and_actor(session, telegram_id=callback.from_user.id)
    data = await state.get_data()
    draft = data["draft"]
    amount = Decimal(str(draft["amount"]))
    currency = draft["currency"]
    account_id = draft["account_id"]
    category_id = await resolve_category_id(session, draft.get("category_slug"))
    tx_type = draft.get("transaction_type", "expense")
    transaction_date = None
    if draft.get("transaction_date"):
        raw_date = draft["transaction_date"]
        transaction_date = date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date

    if tx_type == "income":
        tx, account = await record_income(
            session, user.id, account_id, amount, currency,
            actor_user_id=actor.id,
            description=draft.get("description"),
            transaction_date=transaction_date,
            source_message_id=callback.message.message_id,
            raw_input=draft.get("raw_input"),
        )
    else:
        settlement = Decimal(str(draft["settlement_amount"])) if draft.get("settlement_amount") else None
        tx, account = await record_expense(
            session,
            user.id,
            account_id,
            amount,
            currency,
            actor_user_id=actor.id,
            settlement_amount=settlement,
            settlement_currency=draft.get("settlement_currency"),
            category_id=category_id,
            merchant=draft.get("merchant"),
            description=draft.get("description"),
            transaction_date=transaction_date,
            source_message_id=callback.message.message_id,
            raw_input=draft.get("raw_input"),
        )

    await state.clear()
    saved_line = f"Записал ✅ #{tx.id}"
    if tx.counter_amount:
        saved_line += f"\nВ отчёте: {tx.amount} {tx.currency}, с карты: {tx.counter_amount} {tx.counter_currency}"
    saved_line += f"\nБаланс {account.name}: {balance_service.format_money(account.balance, account.currency)}"
    await callback.message.edit_text(saved_line)
    await callback.answer()


@router.callback_query(F.data == "draft:cancel")
async def cancel_draft(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()
