import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from src.bot.keyboards import (
    ACCOUNT_TYPE_SHORT,
    account_edit_keyboard,
    account_type_keyboard,
    accounts_hub_keyboard,
    currency_keyboard,
)
from src.bot.states import AddAccountStates, EditAccountStates
from src.domain.enums import AccountType
from src.repositories import account_repo, user_repo
from src.services import balance_service

router = Router()


def _format_account_card(account) -> str:
    type_label = ACCOUNT_TYPE_SHORT.get(account.account_type, account.account_type.value)
    return (
        f"*{account.name}*\n"
        f"Тип: {type_label} · Баланс: {balance_service.format_money(account.balance, account.currency)}"
    )


async def show_accounts_hub(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    if not accounts:
        text = "Счетов пока нет. Добавь первый:"
    else:
        text = "*Счета:*\n\n" + balance_service.format_accounts_grouped(accounts)
    await message.answer(text, reply_markup=accounts_hub_keyboard(accounts), parse_mode="Markdown")


async def _show_account_edit(callback: CallbackQuery, session: AsyncSession, account_id: int) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    account = await account_repo.get_account_by_id(session, user.id, account_id)
    if not account:
        await callback.answer("Счёт не найден", show_alert=True)
        return
    await callback.message.edit_text(
        _format_account_card(account),
        reply_markup=account_edit_keyboard(account_id),
        parse_mode="Markdown",
    )


@router.message(Command("add_account"))
async def cmd_add_account(message: Message, state: FSMContext) -> None:
    await state.set_state(AddAccountStates.name)
    await message.answer("Как назовём счёт? Например: Visa RSD, Наличные, Бизнес-счёт")


@router.message(Command("accounts"))
async def cmd_accounts(message: Message, session: AsyncSession) -> None:
    await show_accounts_hub(message, session)


@router.callback_query(F.data == "acct_add")
async def cb_acct_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountStates.name)
    await callback.message.answer("Как назовём счёт? Например: Visa RSD, Наличные, Бизнес-счёт")
    await callback.answer()


@router.callback_query(F.data == "acct_back")
async def cb_acct_back(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    text = "*Счета:*\n\n" + balance_service.format_accounts_grouped(accounts) if accounts else "Счетов пока нет."
    await callback.message.edit_text(
        text,
        reply_markup=accounts_hub_keyboard(accounts),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acct_open:"))
async def cb_acct_open(callback: CallbackQuery, session: AsyncSession) -> None:
    account_id = int(callback.data.split(":")[1])
    await _show_account_edit(callback, session, account_id)
    await callback.answer()


@router.message(AddAccountStates.name)
async def process_account_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое. Попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(AddAccountStates.currency)
    await message.answer("Валюта счёта?", reply_markup=currency_keyboard())


@router.callback_query(AddAccountStates.currency, F.data.startswith("currency:"))
async def process_account_currency(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    currency = callback.data.split(":")[1]
    await state.update_data(currency=currency)
    await state.set_state(AddAccountStates.balance)
    await callback.message.edit_text(f"Валюта: {currency}\n\nТекущий баланс? (0 если не знаешь)")


@router.message(AddAccountStates.balance)
async def process_account_balance(message: Message, state: FSMContext) -> None:
    try:
        balance = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Не понял сумму. Введи число, например: 50000")
        return
    # FSM в Redis хранит JSON — Decimal не сериализуется
    await state.update_data(balance=str(balance))
    await state.set_state(AddAccountStates.account_type)
    await message.answer("Тип счёта?", reply_markup=account_type_keyboard())


@router.callback_query(AddAccountStates.account_type, F.data.startswith("acct_type:"))
async def process_account_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    try:
        account_type = AccountType(callback.data.split(":")[1])
    except ValueError:
        await callback.message.answer("Неизвестный тип счёта. Начни добавление заново: ➕ Добавить счёт")
        await state.clear()
        return

    data = await state.get_data()
    name = data.get("name")
    currency = data.get("currency")
    balance = data.get("balance")
    if not name or not currency or balance is None:
        await callback.message.answer("Данные устарели. Начни добавление счёта заново: ➕ Добавить счёт")
        await state.clear()
        return

    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    existing = await account_repo.get_account_by_name(session, user.id, name)
    if existing:
        await callback.message.answer(f"Счёт «{name}» уже есть. Выбери другое название.")
        await state.set_state(AddAccountStates.name)
        return

    try:
        account = await account_repo.create_account(
            session,
            user_id=user.id,
            name=name,
            currency=currency,
            balance=Decimal(str(balance)),
            account_type=account_type,
        )
    except IntegrityError:
        await callback.message.answer(f"Счёт «{name}» уже существует. Выбери другое название.")
        await state.set_state(AddAccountStates.name)
        return
    except Exception:
        logger.exception("Failed to create account for user %s", user.id)
        await callback.message.answer("Не удалось создать счёт. Попробуй ещё раз.")
        return

    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"Счёт добавлен ✅\n"
        f"{account.name}: {balance_service.format_money(account.balance, account.currency)}"
    )


@router.callback_query(F.data.startswith("acct_type:"))
async def stale_account_type_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Отвечает на callback, если FSM-состояние потеряно (Redis / перезапуск)."""
    await callback.answer("Сессия устарела. Нажми ➕ Добавить счёт и пройди шаги заново.", show_alert=True)
    await state.clear()


@router.callback_query(F.data.startswith("acct_edit_name:"))
async def cb_edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    account_id = int(callback.data.split(":")[1])
    await state.set_state(EditAccountStates.waiting_name)
    await state.update_data(edit_account_id=account_id)
    await callback.message.answer("Новое название счёта:")
    await callback.answer()


@router.message(EditAccountStates.waiting_name)
async def process_edit_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое. Попробуй ещё раз.")
        return
    data = await state.get_data()
    account_id = data["edit_account_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    existing = await account_repo.get_account_by_name(session, user.id, name)
    if existing and existing.id != account_id:
        await message.answer("Счёт с таким названием уже есть.")
        return
    account = await account_repo.update_account(session, user.id, account_id, name=name)
    await state.clear()
    if not account:
        await message.answer("Счёт не найден.")
        return
    await message.answer(f"Название обновлено: *{account.name}*", parse_mode="Markdown")


@router.callback_query(F.data.startswith("acct_edit_currency:"))
async def cb_edit_currency(callback: CallbackQuery, session: AsyncSession) -> None:
    account_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    tx_count = await account_repo.count_for_account(session, account_id)
    if tx_count > 0:
        await callback.answer(
            "Нельзя сменить валюту — на счёте уже есть операции. Создай новый счёт и переведи баланс.",
            show_alert=True,
        )
        return
    await callback.message.edit_text(
        "Выбери новую валюту:",
        reply_markup=currency_keyboard(f"edit_currency:{account_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_currency:"))
async def cb_edit_currency_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    account_id = int(parts[1])
    currency = parts[2]
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    account = await account_repo.update_account(session, user.id, account_id, currency=currency.upper())
    if not account:
        await callback.answer("Счёт не найден", show_alert=True)
        return
    await _show_account_edit(callback, session, account_id)
    await callback.answer("Валюта обновлена")


@router.callback_query(F.data.startswith("acct_edit_balance:"))
async def cb_edit_balance(callback: CallbackQuery, state: FSMContext) -> None:
    account_id = int(callback.data.split(":")[1])
    await state.set_state(EditAccountStates.waiting_balance)
    await state.update_data(edit_account_id=account_id)
    await callback.message.answer("Новый баланс счёта (заменит текущий):")
    await callback.answer()


@router.message(EditAccountStates.waiting_balance)
async def process_edit_balance(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        balance = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Не понял сумму. Введи число, например: 50000")
        return
    data = await state.get_data()
    account_id = data["edit_account_id"]
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    account = await account_repo.update_account(session, user.id, account_id, balance=balance)
    await state.clear()
    if not account:
        await message.answer("Счёт не найден.")
        return
    await message.answer(
        f"Баланс обновлён: {balance_service.format_money(account.balance, account.currency)}"
    )


@router.callback_query(F.data.startswith("acct_edit_type:"))
async def cb_edit_type(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "Выбери тип счёта:",
        reply_markup=account_type_keyboard(f"edit_type:{account_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_type:"))
async def cb_edit_type_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    account_id = int(parts[1])
    account_type = AccountType(parts[2])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    account = await account_repo.update_account(session, user.id, account_id, account_type=account_type)
    if not account:
        await callback.answer("Счёт не найден", show_alert=True)
        return
    await _show_account_edit(callback, session, account_id)
    await callback.answer("Тип обновлён")


@router.callback_query(F.data.startswith("acct_deactivate:"))
async def cb_deactivate(callback: CallbackQuery, session: AsyncSession) -> None:
    account_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    ok = await account_repo.deactivate_account(session, user.id, account_id)
    if not ok:
        await callback.answer("Счёт не найден", show_alert=True)
        return
    accounts = await account_repo.list_accounts(session, user.id)
    text = "*Счета:*\n\n" + balance_service.format_accounts_grouped(accounts) if accounts else "Счетов пока нет."
    await callback.message.edit_text(
        text,
        reply_markup=accounts_hub_keyboard(accounts),
        parse_mode="Markdown",
    )
    await callback.answer("Счёт деактивирован")
