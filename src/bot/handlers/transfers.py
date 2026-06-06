from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import accounts_keyboard
from src.bot.states import TransferStates
from src.repositories import account_repo, fx_repo, user_repo
from src.services import balance_service
from src.services.fx_service import convert
from src.services.transaction_service import record_transfer

router = Router()


@router.message(Command("transfer"))
async def cmd_transfer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    if len(accounts) < 2:
        await message.answer("Нужно минимум 2 счёта. /add_account")
        return
    await state.update_data(transfer_flow=True, telegram_id=message.from_user.id)
    await message.answer("С какого счёта перевести?", reply_markup=accounts_keyboard(accounts, "xfer_from"))


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
    accounts = [a for a in await account_repo.list_accounts(session, user.id) if a.id != from_id]
    await state.update_data(xfer_from=from_id)
    await callback.message.edit_text("На какой счёт?")
    await callback.message.answer("Выбери:", reply_markup=accounts_keyboard(accounts, "xfer_to"))
    await callback.answer()


@router.callback_query(F.data.startswith("xfer_to:"))
async def xfer_to(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("transfer_flow"):
        return
    to_id = int(callback.data.split(":")[1])
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
    user = await user_repo.get_or_create_user(session, telegram_id=data.get("telegram_id", message.from_user.id))
    from_acc = await account_repo.get_account_by_id(session, user.id, data["xfer_from"])
    to_acc = await account_repo.get_account_by_id(session, user.id, data["xfer_to"])

    if from_acc.currency != to_acc.currency:
        converted = await convert(session, amount, from_acc.currency, to_acc.currency)
        if not converted:
            await message.answer(
                f"Нужен курс {from_acc.currency}→{to_acc.currency}.\n"
                f"/set_rate {from_acc.currency} {to_acc.currency} 117.5"
            )
            await state.clear()
            return
        from src.services.balance_service import apply_transaction_to_account
        from src.repositories import transaction_repo
        from src.domain.enums import TransactionType, TransactionStatus
        from datetime import date
        await transaction_repo.create_transaction(
            session, user_id=user.id, type=TransactionType.TRANSFER, status=TransactionStatus.CONFIRMED,
            amount=amount, currency=from_acc.currency, account_id=from_acc.id, counter_account_id=to_acc.id,
            description=f"→ {to_acc.name} ({converted} {to_acc.currency})", transaction_date=date.today(),
        )
        apply_transaction_to_account(from_acc, "transfer_out", amount)
        apply_transaction_to_account(to_acc, "transfer_in", converted)
        await message.answer(
            f"Перевод ✅\n{amount} {from_acc.currency} → {converted} {to_acc.currency}\n"
            f"{from_acc.name}: {balance_service.format_money(from_acc.balance, from_acc.currency)}\n"
            f"{to_acc.name}: {balance_service.format_money(to_acc.balance, to_acc.currency)}"
        )
    else:
        await record_transfer(session, user.id, from_acc.id, to_acc.id, amount, from_acc.currency)
        await message.answer(
            f"Перевод ✅ {amount} {from_acc.currency}\n"
            f"{from_acc.name}: {balance_service.format_money(from_acc.balance, from_acc.currency)}\n"
            f"{to_acc.name}: {balance_service.format_money(to_acc.balance, to_acc.currency)}"
        )
    await state.clear()
