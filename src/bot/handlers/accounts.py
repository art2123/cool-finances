from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import account_type_keyboard, currency_keyboard
from src.bot.states import AddAccountStates
from src.domain.enums import AccountType
from src.repositories import account_repo, user_repo
from src.services import balance_service

router = Router()


@router.message(Command("add_account"))
async def cmd_add_account(message: Message, state: FSMContext) -> None:
    await state.set_state(AddAccountStates.name)
    await message.answer("Как назовём счёт? Например: Visa RSD, Наличные, Бизнес-счёт")


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
    currency = callback.data.split(":")[1]
    await state.update_data(currency=currency)
    await state.set_state(AddAccountStates.balance)
    await callback.message.edit_text(f"Валюта: {currency}\n\nТекущий баланс? (0 если не знаешь)")
    await callback.answer()


@router.message(AddAccountStates.balance)
async def process_account_balance(message: Message, state: FSMContext) -> None:
    try:
        balance = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Не понял сумму. Введи число, например: 50000")
        return
    await state.update_data(balance=balance)
    await state.set_state(AddAccountStates.account_type)
    await message.answer("Тип счёта?", reply_markup=account_type_keyboard())


@router.callback_query(AddAccountStates.account_type, F.data.startswith("acct_type:"))
async def process_account_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    account_type = AccountType(callback.data.split(":")[1])
    data = await state.get_data()
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)

    account = await account_repo.create_account(
        session,
        user_id=user.id,
        name=data["name"],
        currency=data["currency"],
        balance=data["balance"],
        account_type=account_type,
    )
    await state.clear()
    await callback.message.edit_text(
        f"Счёт добавлен ✅\n"
        f"{account.name}: {balance_service.format_money(account.balance, account.currency)}"
    )
    await callback.answer()
