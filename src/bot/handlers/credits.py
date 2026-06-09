from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.advisor.interest_calculator import build_interest_report
from src.bot.keyboards import accounts_keyboard
from src.bot.states import CreditTermsStates
from src.domain.enums import AccountType, DebtProductType
from src.repositories import account_repo, credit_repo, user_repo
from src.services import balance_service

router = Router()


@router.message(Command("interest"))
async def cmd_interest(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    debt_accounts = [
        a for a in accounts
        if a.account_type in (AccountType.CREDIT, AccountType.DEBT)
        or (a.account_type == AccountType.DEBIT and a.balance < 0)
    ]
    terms_map = await credit_repo.get_terms_map(session, [a.id for a in debt_accounts])
    await message.answer(build_interest_report(debt_accounts, terms_map), parse_mode="Markdown")


@router.message(Command("debts"))
async def cmd_debts(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    debts = await balance_service.get_debt_totals(session, user.id)
    terms_map = await credit_repo.get_terms_map(session, [a.id for a in accounts])
    debt_list = [a for a in accounts if a.account_type in (AccountType.CREDIT, AccountType.DEBT) or a.balance < 0]

    lines = ["*Долги и кредитки:*", balance_service.format_accounts_list(debt_list)]
    if debts:
        lines.extend(["", "*Итого долг:*"])
        for cur, total in debts.items():
            lines.append(f"  {balance_service.format_money(total, cur)}")
    lines.extend(["", build_interest_report(debt_list, terms_map)])
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("credit_terms"))
async def cmd_credit_terms(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = [
        a for a in await account_repo.list_accounts(session, user.id)
        if a.account_type in (AccountType.CREDIT, AccountType.DEBT)
    ]
    if not accounts:
        await message.answer("Нет кредитных счетов. Нажми ➕ Счёт и выбери тип «кредитка» или «долг»")
        return
    await message.answer("Для какого счёта задать условия?", reply_markup=accounts_keyboard(accounts, "credit_acct"))


@router.callback_query(F.data.startswith("credit_acct:"))
async def credit_terms_account(callback: CallbackQuery, state: FSMContext) -> None:
    account_id = int(callback.data.split(":")[1])
    await state.set_state(CreditTermsStates.waiting_rate)
    await state.update_data(credit_account_id=account_id)
    await callback.message.edit_text("Годовая ставка %? (например: 19.9)")
    await callback.answer()


@router.message(CreditTermsStates.waiting_rate)
async def credit_terms_rate(message: Message, state: FSMContext) -> None:
    try:
        rate = Decimal(message.text.replace(",", "."))
    except InvalidOperation:
        await message.answer("Введи число, например: 19.9")
        return
    await state.update_data(credit_rate=rate)
    await state.set_state(CreditTermsStates.waiting_min_payment)
    await message.answer("Минимальный платёж? (0 если не знаешь)")


@router.message(CreditTermsStates.waiting_min_payment)
async def credit_terms_min_payment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        min_pay = Decimal(message.text.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        await message.answer("Введи число")
        return

    data = await state.get_data()
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    account = await account_repo.get_account_by_id(session, user.id, data["credit_account_id"])

    product = DebtProductType.CREDIT_CARD
    if account.account_type == AccountType.DEBT:
        product = DebtProductType.PERSONAL_DEBT
    elif account.account_type == AccountType.DEBIT and account.balance < 0:
        product = DebtProductType.OVERDRAFT

    await credit_repo.upsert_terms(
        session,
        account_id=account.id,
        product_type=product,
        calc_method=credit_repo.default_calc_method(product),
        interest_rate_annual=data["credit_rate"],
        min_payment=min_pay if min_pay > 0 else None,
        terms_confirmed=True,
    )
    await state.clear()
    await message.answer(
        f"Условия сохранены ✅\n{account.name}: ставка {data['credit_rate']}%"
        + (f", мин. платёж {min_pay}" if min_pay > 0 else "")
    )
