from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import accounts_keyboard, format_account_label
from src.bot.states import TransferStates
from src.repositories import account_repo, fx_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import record_transfer

router = Router()


@router.message(Command("transfer"))
async def cmd_transfer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    if len(accounts) < 2:
        await message.answer("Нужно минимум 2 счёта. Нажми ➕ Счёт")
        return
    await state.update_data(transfer_flow=True, telegram_id=message.from_user.id)
    await message.answer(
        "Перевод в одной валюте между своими счетами.\n"
        "Для обмена валют / крипты — кнопка 🔄 Конвертация.\n\n"
        "С какого счёта перевести?",
        reply_markup=accounts_keyboard(accounts, "xfer_from"),
    )


@router.message(Command("set_rate"))
async def cmd_set_rate(message: Message, session: AsyncSession) -> None:
    parts = (message.text or "").split()
    if len(parts) < 4:
        await message.answer("Формат: /set_rate RSD EUR 117.5")
        return
    try:
        rate = Decimal(parts[3].replace(",", "."))
        await fx_repo.set_rate(session, parts[1].upper(), parts[2].upper(), rate)
        await message.answer(f"Курс {parts[1]}→{parts[2]}: {rate} ✅")
    except InvalidOperation:
        await message.answer("Неверный курс")


@router.callback_query(F.data.startswith("xfer_from:"))
async def xfer_from(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if not data.get("transfer_flow"):
        return
    from_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    from_acc = await account_repo.get_account_by_id(session, user.id, from_id)
    accounts = [a for a in await account_repo.list_accounts(session, user.id) if a.id != from_id]
    await state.update_data(xfer_from=from_id)
    await callback.message.edit_text(
        f"С: {format_account_label(from_acc)} ({from_acc.currency})\n\n"
        "На какой счёт? (другая валюта → 🔄 Конвертация)"
    )
    await callback.message.answer("Выбери:", reply_markup=accounts_keyboard(accounts, "xfer_to"))
    await callback.answer()


@router.callback_query(F.data.startswith("xfer_to:"))
async def xfer_to(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if not data.get("transfer_flow"):
        return
    to_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    from_acc = await account_repo.get_account_by_id(session, user.id, data["xfer_from"])
    to_acc = await account_repo.get_account_by_id(session, user.id, to_id)

    if from_acc.currency != to_acc.currency:
        await callback.message.edit_text(
            f"Счета в разных валютах ({from_acc.currency} → {to_acc.currency}).\n"
            "Для обмена нажми 🔄 Конвертация — укажешь сколько ушло и сколько пришло."
        )
        await state.clear()
        await callback.answer()
        return

    await state.update_data(xfer_to=to_id)
    await state.set_state(TransferStates.waiting_amount)
    await callback.message.edit_text("Сумма перевода?")
    await callback.answer()


@router.message(TransferStates.waiting_amount)
async def xfer_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число")
        return

    data = await state.get_data()
    telegram_id = data.get("telegram_id", message.from_user.id)
    user, actor = await user_repo.resolve_data_and_actor(session, telegram_id=telegram_id)
    from_acc = await account_repo.get_account_by_id(session, user.id, data["xfer_from"])
    to_acc = await account_repo.get_account_by_id(session, user.id, data["xfer_to"])

    await record_transfer(
        session, user.id, from_acc.id, to_acc.id, amount, from_acc.currency, actor_user_id=actor.id
    )
    await state.clear()
    await message.answer(
        f"Перевод ✅ {amount} {from_acc.currency}\n"
        f"{from_acc.name}: {balance_service.format_money(from_acc.balance, from_acc.currency)}\n"
        f"{to_acc.name}: {balance_service.format_money(to_acc.balance, to_acc.currency)}"
    )
