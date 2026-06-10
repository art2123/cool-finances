from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import (
    accounts_keyboard,
    categories_keyboard,
    currency_keyboard,
    expense_accounts_keyboard,
    transaction_edit_keyboard,
    transaction_list_keyboard,
)
from src.bot.states import EditTransactionStates
from src.domain.enums import TransactionType, transaction_type_label
from src.models.transaction import Transaction
from src.repositories import account_repo, category_repo, transaction_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import resolve_category_id, update_transaction

router = Router()

PAGE_SIZE = 10


def _tx_title(tx: Transaction) -> str:
    return tx.merchant or (tx.category.name if tx.category else None) or tx.description or "Операция"


def format_tx_line(tx: Transaction) -> str:
    title = _tx_title(tx)
    day = tx.transaction_date.strftime("%d.%m")

    if tx.type == TransactionType.EXPENSE:
        base = balance_service.format_money(tx.amount, tx.currency)
        if tx.counter_amount:
            base = f"{base} → {balance_service.format_money(tx.counter_amount, tx.counter_currency or tx.currency)}"
        account_name = tx.account.name if tx.account else "?"
        return f"#{tx.id} · {base} · {title} · {account_name} · {day}"

    if tx.type == TransactionType.INCOME:
        account_name = tx.account.name if tx.account else "?"
        return f"#{tx.id} · +{balance_service.format_money(tx.amount, tx.currency)} · {title} · {account_name} · {day}"

    if tx.type == TransactionType.CONVERSION:
        from_name = tx.account.name if tx.account else "?"
        to_name = tx.counter_account.name if tx.counter_account else "?"
        return (
            f"#{tx.id} · {balance_service.format_money(tx.amount, tx.currency)} → "
            f"{balance_service.format_money(tx.counter_amount or tx.amount, tx.counter_currency or tx.currency)} · "
            f"{from_name} → {to_name} · {day}"
        )

    if tx.type == TransactionType.TRANSFER:
        from_name = tx.account.name if tx.account else "?"
        to_name = tx.counter_account.name if tx.counter_account else "?"
        return f"#{tx.id} · {balance_service.format_money(tx.amount, tx.currency)} · {from_name} → {to_name} · {day}"

    account_name = tx.account.name if tx.account else "?"
    return f"#{tx.id} · {balance_service.format_money(tx.amount, tx.currency)} · {title} · {account_name} · {day}"


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


def _edit_keyboard_for(tx: Transaction) -> object:
    foreign_expense = tx.type == TransactionType.EXPENSE and tx.counter_amount is not None
    return transaction_edit_keyboard(tx.id, tx.type.value, foreign_expense=foreign_expense)


async def _finish_edit(
    event: Message | CallbackQuery,
    updated: Transaction,
    state: FSMContext,
    *,
    answer_text: str | None = None,
) -> None:
    await _reset_edit_state_keep_history(state)
    data = await state.get_data()
    text = format_tx_card(updated)
    keyboard = _edit_keyboard_for(updated)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await event.answer(answer_text or "Сохранено")
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")


def format_tx_card(tx: Transaction) -> str:
    lines = [
        f"*Операция #{tx.id}*",
        f"Тип: {transaction_type_label(tx.type)}",
        f"Дата: {tx.transaction_date.strftime('%d.%m.%Y')}",
    ]

    if tx.type == TransactionType.EXPENSE:
        lines.append(f"Покупка: {balance_service.format_money(tx.amount, tx.currency)}")
        if tx.counter_amount:
            lines.append(
                f"Списание: {balance_service.format_money(tx.counter_amount, tx.counter_currency or tx.currency)}"
            )
        if tx.account:
            lines.append(f"Счёт: {tx.account.name}")
    elif tx.type == TransactionType.INCOME:
        lines.append(f"Сумма: {balance_service.format_money(tx.amount, tx.currency)}")
        if tx.account:
            lines.append(f"Счёт: {tx.account.name}")
    elif tx.type == TransactionType.CONVERSION:
        lines.append(f"Списано: {balance_service.format_money(tx.amount, tx.currency)}")
        lines.append(
            f"Зачислено: {balance_service.format_money(tx.counter_amount or tx.amount, tx.counter_currency or tx.currency)}"
        )
        if tx.account:
            lines.append(f"Счёт списания: {tx.account.name}")
        if tx.counter_account:
            lines.append(f"Счёт зачисления: {tx.counter_account.name}")
    elif tx.type == TransactionType.TRANSFER:
        lines.append(f"Сумма: {balance_service.format_money(tx.amount, tx.currency)}")
        if tx.account:
            lines.append(f"Счёт откуда: {tx.account.name}")
        if tx.counter_account:
            lines.append(f"Счёт куда: {tx.counter_account.name}")
    else:
        lines.append(f"Сумма: {balance_service.format_money(tx.amount, tx.currency)}")
        if tx.account:
            lines.append(f"Счёт: {tx.account.name}")

    if tx.merchant:
        lines.append(f"Описание: {tx.merchant}")
    if tx.category:
        lines.append(f"Категория: {tx.category.name}")
    if tx.description:
        lines.append(f"Комментарий: {tx.description}")

    return "\n".join(lines)


async def _reset_edit_state_keep_history(state: FSMContext) -> None:
    data = await state.get_data()
    history_data = {key: value for key, value in data.items() if key.startswith("history_")}
    await state.clear()
    if history_data:
        await state.update_data(**history_data)


async def _edit_history_message(
    event: Message | CallbackQuery,
    tx: Transaction,
    *,
    state: FSMContext,
    account_id: int | None = None,
) -> None:
    await state.update_data(history_account_id=account_id)
    text = format_tx_card(tx)
    keyboard = _edit_keyboard_for(tx)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_transaction_history(
    event: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    *,
    account_id: int | None = None,
    page: int = 0,
) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=event.from_user.id)
    offset = page * PAGE_SIZE
    txs = await transaction_repo.list_recent_transactions(
        session,
        user.id,
        limit=PAGE_SIZE,
        offset=offset,
        account_id=account_id,
    )
    total = await transaction_repo.count_recent_transactions(session, user.id, account_id=account_id)
    await state.update_data(history_account_id=account_id, history_page=page)

    scope = ""
    if account_id is not None:
        account = await account_repo.get_account_by_id(session, user.id, account_id)
        if account:
            scope = f" по счёту {account.name}"

    if not txs:
        text = f"Операций{scope} пока нет."
    else:
        lines = [f"*История{scope}:*"]
        lines.extend(f"• {format_tx_line(tx)}" for tx in txs)
        text = "\n".join(lines)

    keyboard = transaction_list_keyboard(
        [(tx, format_tx_line(tx)) for tx in txs],
        page=page,
        total_count=total,
        page_size=PAGE_SIZE,
        account_id=account_id,
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(Command("history"))
async def cmd_history(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").split(maxsplit=1)
    account_id = None
    if len(text) > 1:
        try:
            account_id = int(text[1])
        except ValueError:
            await message.answer("Формат: /history [account_id]")
            return
    await show_transaction_history(message, session, state, account_id=account_id)


@router.callback_query(F.data.startswith("tx_page:"))
async def cb_tx_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, page_str, account_str = callback.data.split(":")
    account_id = int(account_str) if account_str else None
    await show_transaction_history(callback, session, state, account_id=account_id, page=int(page_str))
    await callback.answer()


@router.callback_query(F.data.startswith("tx_open:"))
async def cb_tx_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    tx_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    tx = await transaction_repo.get_transaction_by_id(session, user.id, tx_id)
    if not tx:
        await callback.answer("Операция не найдена", show_alert=True)
        return
    data = await state.get_data()
    await _edit_history_message(callback, tx, state=state, account_id=data.get("history_account_id"))
    await state.update_data(edit_tx_id=tx_id)
    await callback.answer()


@router.callback_query(F.data == "tx_back_list")
async def cb_tx_back_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await show_transaction_history(
        callback,
        session,
        state,
        account_id=data.get("history_account_id"),
        page=data.get("history_page", 0),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tx_edit:"))
async def cb_tx_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, tx_id_str, field = callback.data.split(":")
    tx_id = int(tx_id_str)
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    tx = await transaction_repo.get_transaction_by_id(session, user.id, tx_id)
    if not tx:
        await callback.answer("Операция не найдена", show_alert=True)
        return

    await state.update_data(edit_tx_id=tx_id)

    if field == "amount":
        await state.set_state(EditTransactionStates.waiting_amount)
        await callback.message.answer("Новая сумма?")
    elif field == "currency":
        await state.set_state(EditTransactionStates.waiting_currency)
        await callback.message.answer("Выбери валюту:", reply_markup=currency_keyboard())
    elif field == "settlement":
        await state.set_state(EditTransactionStates.waiting_settlement)
        await callback.message.answer("Сколько списалось с карты?")
    elif field == "counter_amount":
        await state.set_state(EditTransactionStates.waiting_counter_amount)
        await callback.message.answer("Новая сумма зачисления?")
    elif field == "account":
        accounts = await account_repo.list_accounts(session, user.id)
        if tx.type == TransactionType.EXPENSE:
            picker_currency = tx.counter_currency if tx.counter_amount else tx.currency
            await callback.message.answer(
                "Выбери счёт:",
                reply_markup=expense_accounts_keyboard(accounts, picker_currency, prefix=f"tx_pick_account:{tx_id}"),
            )
        else:
            await callback.message.answer(
                "Выбери счёт:",
                reply_markup=accounts_keyboard(accounts, prefix=f"tx_pick_account:{tx_id}"),
            )
    elif field == "counter_account":
        accounts = await account_repo.list_accounts(session, user.id)
        remaining = [account for account in accounts if account.id != tx.account_id]
        await callback.message.answer(
            "Выбери счёт:",
            reply_markup=accounts_keyboard(remaining, prefix=f"tx_pick_counter:{tx_id}"),
        )
    elif field == "date":
        await state.set_state(EditTransactionStates.waiting_date)
        await callback.message.answer("Новая дата? Формат: 10.06.2026")
    elif field == "merchant":
        await state.set_state(EditTransactionStates.waiting_merchant)
        current = tx.merchant or "—"
        await callback.message.answer(f"Текущее описание: {current}\n\nВведи новое (или «-» чтобы очистить):")
    elif field == "description":
        await state.set_state(EditTransactionStates.waiting_description)
        current = tx.description or "—"
        await callback.message.answer(f"Текущий комментарий: {current}\n\nВведи новый (или «-» чтобы очистить):")
    elif field == "category":
        categories = await category_repo.list_categories(session)
        await callback.message.answer(
            "Выбери категорию:",
            reply_markup=categories_keyboard(categories, prefix=f"tx_cat:{tx_id}"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("tx_pick_account:"))
async def cb_tx_pick_account(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, tx_id_str, account_id_str = callback.data.split(":")
    tx_id = int(tx_id_str)
    account_id = int(account_id_str)
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    tx = await transaction_repo.get_transaction_by_id(session, user.id, tx_id)
    account = await account_repo.get_account_by_id(session, user.id, account_id)
    if not tx or not account:
        await callback.answer("Операция или счёт не найдены", show_alert=True)
        return

    await state.update_data(edit_tx_id=tx_id)
    if tx.type == TransactionType.EXPENSE and tx.currency.upper() != account.currency.upper():
        await state.set_state(EditTransactionStates.waiting_settlement)
        await state.update_data(pending_account_id=account_id, pending_currency=None)
        await callback.message.answer(
            f"Новая карта в {account.currency}.\nСколько списалось с карты?"
        )
        await callback.answer()
        return

    try:
        updated = await update_transaction(session, user.id, tx_id, account_id=account_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await _edit_history_message(callback, updated, state=state, account_id=(await state.get_data()).get("history_account_id"))
    await _reset_edit_state_keep_history(state)
    await callback.answer("Счёт обновлён")


@router.callback_query(F.data.startswith("tx_pick_counter:"))
async def cb_tx_pick_counter(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, tx_id_str, account_id_str = callback.data.split(":")
    tx_id = int(tx_id_str)
    account_id = int(account_id_str)
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    tx = await transaction_repo.get_transaction_by_id(session, user.id, tx_id)
    if not tx:
        await callback.answer("Операция не найдена", show_alert=True)
        return

    try:
        updated = await update_transaction(session, user.id, tx_id, counter_account_id=account_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await _edit_history_message(callback, updated, state=state, account_id=(await state.get_data()).get("history_account_id"))
    await _reset_edit_state_keep_history(state)
    await callback.answer("Счёт обновлён")


@router.message(EditTransactionStates.waiting_amount)
async def process_edit_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 200")
        return
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    try:
        updated = await update_transaction(session, user.id, tx_id, amount=amount)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_edit(message, updated, state)


@router.callback_query(F.data.startswith("tx_cat:"))
async def cb_tx_pick_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, tx_id_str, slug = callback.data.split(":")
    tx_id = int(tx_id_str)
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    category_id = await resolve_category_id(session, slug)
    try:
        updated = await update_transaction(session, user.id, tx_id, category_id=category_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await _finish_edit(callback, updated, state, answer_text="Категория обновлена")


@router.callback_query(EditTransactionStates.waiting_currency, F.data.startswith("currency:"))
async def process_edit_currency(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    currency = callback.data.split(":")[1]
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    tx = await transaction_repo.get_transaction_by_id(session, user.id, tx_id)
    if not tx:
        await callback.answer("Операция не найдена", show_alert=True)
        return
    account = await account_repo.get_account_by_id(session, user.id, tx.account_id)
    if tx.type == TransactionType.EXPENSE and account and account.currency.upper() != currency.upper() and tx.counter_amount is None:
        await state.set_state(EditTransactionStates.waiting_settlement)
        await state.update_data(pending_currency=currency.upper(), pending_account_id=None)
        await callback.message.answer("Нужна сумма списания с карты:")
        await callback.answer()
        return
    try:
        updated = await update_transaction(session, user.id, tx_id, currency=currency)
    except ValueError as exc:
        await callback.message.answer(str(exc))
        await callback.answer()
        return
    await _finish_edit(callback, updated, state, answer_text="Валюта обновлена")


@router.message(EditTransactionStates.waiting_settlement)
async def process_edit_settlement(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 1680")
        return
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    kwargs = {"counter_amount": amount}
    if data.get("pending_account_id") is not None:
        kwargs["account_id"] = data["pending_account_id"]
    if data.get("pending_currency"):
        kwargs["currency"] = data["pending_currency"]
    try:
        updated = await update_transaction(session, user.id, tx_id, **kwargs)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_edit(message, updated, state)


@router.message(EditTransactionStates.waiting_date)
async def process_edit_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        new_date = _parse_date_input(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    try:
        updated = await update_transaction(session, user.id, tx_id, transaction_date=new_date)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_edit(message, updated, state)


@router.message(EditTransactionStates.waiting_merchant)
async def process_edit_merchant(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    merchant = None if text in {"-", "—", ""} else text
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    try:
        updated = await update_transaction(session, user.id, tx_id, merchant=merchant)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_edit(message, updated, state)


@router.message(EditTransactionStates.waiting_description)
async def process_edit_description(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    description = None if text in {"-", "—", ""} else text
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    try:
        updated = await update_transaction(session, user.id, tx_id, description=description)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_edit(message, updated, state)


@router.message(EditTransactionStates.waiting_counter_amount)
async def process_edit_counter_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 25000")
        return
    data = await state.get_data()
    tx_id = data["edit_tx_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    try:
        updated = await update_transaction(session, user.id, tx_id, counter_amount=amount)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await _finish_edit(message, updated, state)
