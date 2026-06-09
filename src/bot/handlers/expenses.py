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
    accounts_keyboard,
    categories_keyboard,
    confirm_keyboard,
    currency_keyboard,
)
from src.bot.states import ExpenseStates
from src.domain.enums import TransactionType, UserIntent
from src.parsers.intent_classifier import classify_intent
from src.parsers.text_expense_parser import parse_expense_text
from src.repositories import account_repo, category_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import (
    draft_missing_fields,
    pick_default_account,
    record_expense,
    record_income,
    resolve_category_id,
)
from src.domain.schemas import ExpenseDraft

router = Router()


def format_draft_preview(draft: dict, account_name: str = None) -> str:
    lines = ["*Черновик операции:*"]
    lines.append(f"Тип: {draft.get('transaction_type', 'expense')}")
    if draft.get("amount"):
        lines.append(f"Покупка: {draft['amount']} {draft.get('currency', '?')}")
    if draft.get("settlement_amount"):
        cur = draft.get("settlement_currency") or "?"
        lines.append(f"Списание с карты: {draft['settlement_amount']} {cur}")
    if draft.get("merchant"):
        lines.append(f"Место: {draft['merchant']}")
    if draft.get("category_slug"):
        lines.append(f"Категория: {draft['category_slug']}")
    if account_name:
        lines.append(f"Счёт: {account_name}")
    return "\n".join(lines)


async def start_expense_flow(message: Message, state: FSMContext, session: AsyncSession, text: str) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    await category_repo.ensure_system_categories(session)

    draft = await parse_expense_text(text)
    account = await pick_default_account(session, user.id, draft.currency, draft.account_name)

    payload = draft.model_dump(mode="json")
    if account:
        payload["account_id"] = account.id
        payload["account_name"] = account.name

    await state.update_data(draft=payload, telegram_id=message.from_user.id)
    missing = draft_missing_fields(draft, account)

    if "amount" in missing:
        await state.set_state(ExpenseStates.waiting_amount)
        await message.answer("Какая сумма?")
        return
    if "currency" in missing:
        await state.set_state(ExpenseStates.waiting_currency)
        await message.answer("В какой валюте?", reply_markup=currency_keyboard())
        return
    if "account" in missing:
        accounts = await account_repo.list_accounts(session, user.id)
        await state.set_state(ExpenseStates.waiting_account)
        await message.answer("С какого счёта?", reply_markup=accounts_keyboard(accounts))
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

    await state.set_state(ExpenseStates.confirm)
    await message.answer(
        format_draft_preview(payload, account.name if account else None),
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown",
    )


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
    await state.update_data(draft=draft)
    await callback.message.edit_text(f"Валюта: {currency}")
    await callback.answer()
    await _continue_draft(callback.message, state, session)


@router.callback_query(ExpenseStates.waiting_account, F.data.startswith("pick_account:"))
async def process_draft_account(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    account_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    account = await account_repo.get_account_by_id(session, user.id, account_id)
    data = await state.get_data()
    draft = data["draft"]
    draft["account_id"] = account_id
    draft["account_name"] = account.name if account else None
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
    if draft_data.get("account_id"):
        account = await account_repo.get_account_by_id(session, user.id, draft_data["account_id"])
    else:
        account = await pick_default_account(session, user.id, draft.currency)

    missing = draft_missing_fields(draft, account)
    if "currency" in missing:
        await state.set_state(ExpenseStates.waiting_currency)
        await message.answer("В какой валюте?", reply_markup=currency_keyboard())
        return
    if "account" in missing:
        accounts = await account_repo.list_accounts(session, user.id)
        await state.set_state(ExpenseStates.waiting_account)
        await message.answer("С какого счёта?", reply_markup=accounts_keyboard(accounts))
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

    await state.set_state(ExpenseStates.confirm)
    await message.answer(
        format_draft_preview(draft_data, draft_data.get("account_name")),
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown",
    )


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

    if tx_type == "income":
        tx, account = await record_income(
            session, user.id, account_id, amount, currency,
            actor_user_id=actor.id,
            description=draft.get("description"),
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
