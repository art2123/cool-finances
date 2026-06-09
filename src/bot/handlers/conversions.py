from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import accounts_keyboard
from src.bot.states import ConversionStates
from src.repositories import account_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import record_conversion

router = Router()


async def cmd_conversion(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    if len(accounts) < 2:
        await message.answer("Нужно минимум 2 счёта в разных валютах. Нажми ➕ Счёт")
        return
    await state.update_data(conversion_flow=True, telegram_id=message.from_user.id)
    await message.answer(
        "🔄 *Конвертация* — обмен или крипта, не трата.\n"
        "Пример: 5000 RUB → 25000 KZT через биржу.\n\n"
        "С какого счёта списать?",
        parse_mode="Markdown",
        reply_markup=accounts_keyboard(accounts, "conv_from"),
    )


@router.message(Command("convert"))
async def cmd_convert(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await cmd_conversion(message, state, session)


@router.callback_query(F.data.startswith("conv_from:"))
async def conv_from(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if not data.get("conversion_flow"):
        return
    from_id = int(callback.data.split(":")[1])
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    from_acc = await account_repo.get_account_by_id(session, user.id, from_id)
    accounts = [
        a
        for a in await account_repo.list_accounts(session, user.id)
        if a.id != from_id and a.currency != from_acc.currency
    ]
    if not accounts:
        await callback.message.edit_text(
            f"Нет счетов в другой валюте для обмена с {from_acc.name} ({from_acc.currency}).\n"
            "Добавь счёт в нужной валюте: ➕ Счёт"
        )
        await state.clear()
        await callback.answer()
        return
    await state.update_data(conv_from=from_id)
    await callback.message.edit_text(
        f"Списываем с: {from_acc.name} ({from_acc.currency})\n\nНа какой счёт зачислить?"
    )
    await callback.message.answer("Выбери:", reply_markup=accounts_keyboard(accounts, "conv_to"))
    await callback.answer()


@router.callback_query(F.data.startswith("conv_to:"))
async def conv_to(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if not data.get("conversion_flow"):
        return
    to_id = int(callback.data.split(":")[1])
    await state.update_data(conv_to=to_id)
    await state.set_state(ConversionStates.waiting_amount_out)
    await callback.message.edit_text("Сколько списать с исходного счёта?")
    await callback.answer()


@router.message(ConversionStates.waiting_amount_out)
async def conv_amount_out(message: Message, state: FSMContext) -> None:
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 5000")
        return
    await state.update_data(conv_amount_out=str(amount))
    await state.set_state(ConversionStates.waiting_amount_in)
    await message.answer("Сколько пришло на счёт назначения? (фактическая сумма после обмена)")


@router.message(ConversionStates.waiting_amount_in)
async def conv_amount_in(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount_in = Decimal(message.text.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 25000")
        return

    data = await state.get_data()
    user = await user_repo.get_or_create_user(session, telegram_id=data.get("telegram_id", message.from_user.id))
    amount_out = Decimal(str(data["conv_amount_out"]))
    from_acc = await account_repo.get_account_by_id(session, user.id, data["conv_from"])
    to_acc = await account_repo.get_account_by_id(session, user.id, data["conv_to"])

    await record_conversion(session, user.id, from_acc.id, to_acc.id, amount_out, amount_in)
    await state.clear()
    await message.answer(
        f"Конвертация ✅\n"
        f"−{balance_service.format_money(amount_out, from_acc.currency)} ({from_acc.name})\n"
        f"+{balance_service.format_money(amount_in, to_acc.currency)} ({to_acc.name})\n\n"
        f"Это не трата и не доход — деньги просто сменили валюту/счёт."
    )
