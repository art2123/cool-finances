from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.advisor.cashflow_forecast import build_month_forecast
from src.advisor.interest_calculator import build_interest_report
from src.advisor.purchase_advice import advise_purchase
from src.advisor.what_if_simulator import compare_payment_targets, simulate_extra_payment
from src.domain.enums import AccountType, UserIntent
from src.parsers.intent_classifier import ClassifiedIntent, classify_intent, _extract_amount
from src.repositories import account_repo, credit_repo, goals_repo, recurring_repo, transaction_repo, user_repo
from src.services import balance_service

router = Router()


async def handle_classified_intent(
    message: Message,
    session: AsyncSession,
    classified: ClassifiedIntent,
) -> bool:
    """Returns True if handled."""
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    text = message.text or ""

    if classified.intent == UserIntent.INTEREST:
        debt_accounts = [a for a in accounts if a.account_type in (AccountType.CREDIT, AccountType.DEBT)]
        terms_map = await credit_repo.get_terms_map(session, [a.id for a in debt_accounts])
        await message.answer(build_interest_report(debt_accounts, terms_map), parse_mode="Markdown")
        return True

    if classified.intent == UserIntent.WHAT_IF:
        amount = classified.amount or _extract_amount(text.lower())
        if not amount:
            await message.answer("Укажи сумму: «что будет, если 50000 закину на Visa»")
            return True
        debt_accounts = [a for a in accounts if a.account_type in (AccountType.CREDIT, AccountType.DEBT)]
        if not debt_accounts:
            await message.answer("Нет долговых счетов. Добавь кредитку: /add_account")
            return True
        target = debt_accounts[0]
        for a in debt_accounts:
            if a.name.lower() in text.lower():
                target = a
                break
        terms = await credit_repo.get_terms(session, target.id)
        goals = await goals_repo.list_goals(session, user.id)
        emergency = next((g.target_amount for g in goals if g.is_emergency_fund and g.currency == target.currency), Decimal("0"))
        cash = [a for a in accounts if a.account_type in (AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS)]
        result = simulate_extra_payment(target, terms, amount, cash, emergency)
        await message.answer(result.message, parse_mode="Markdown")

        if len(debt_accounts) > 1:
            targets = [(a, await credit_repo.get_terms(session, a.id)) for a in debt_accounts]
            cmp = compare_payment_targets(amount, targets, cash)
            await message.answer(cmp, parse_mode="Markdown")
        return True

    if classified.intent in (UserIntent.AFFORDABILITY, UserIntent.PURCHASE_ADVICE):
        amount = classified.amount or _extract_amount(text.lower()) or Decimal("0")
        currency = "EUR" if "евро" in text.lower() or "eur" in text.lower() else "RSD"
        goals = await goals_repo.list_goals(session, user.id)
        recurring = await recurring_repo.list_recurring(session, user.id)
        mandatory = sum(r.amount for r in recurring if r.is_mandatory and not r.is_income and r.currency == currency)
        if "следующ" in text.lower() or "след" in text.lower():
            forecast = build_month_forecast(accounts, recurring, goals, {}, amount, currency)
            await message.answer(forecast.message, parse_mode="Markdown")
        else:
            await message.answer(advise_purchase(amount, currency, accounts, goals, mandatory), parse_mode="Markdown")
        return True

    if classified.intent == UserIntent.SAVINGS_PROJECTION:
        amount = classified.amount or _extract_amount(text.lower())
        if not amount:
            await message.answer("Укажи сумму трат: «сколько отложу, если потрачу 130000»")
            return True
        recurring = await recurring_repo.list_recurring(session, user.id)
        goals = await goals_repo.list_goals(session, user.id)
        forecast = build_month_forecast(accounts, recurring, goals, {}, hypothetical_spending=amount)
        await message.answer(forecast.message, parse_mode="Markdown")
        return True

    if classified.intent == UserIntent.FORECAST:
        recurring = await recurring_repo.list_recurring(session, user.id)
        goals = await goals_repo.list_goals(session, user.id)
        since = transaction_repo.period_start("month")
        totals = await transaction_repo.get_expenses_sum(session, user.id, since)
        forecast = build_month_forecast(accounts, recurring, goals, totals)
        await message.answer(forecast.message, parse_mode="Markdown")
        return True

    if classified.intent == UserIntent.DEBTS:
        debt_accounts = [a for a in accounts if a.account_type in (AccountType.CREDIT, AccountType.DEBT)]
        terms_map = await credit_repo.get_terms_map(session, [a.id for a in debt_accounts])
        lines = ["*Долги:*", balance_service.format_accounts_list(debt_accounts), "", build_interest_report(debt_accounts, terms_map)]
        await message.answer("\n".join(lines), parse_mode="Markdown")
        return True

    return False


@router.message(Command("forecast"))
async def cmd_forecast(message: Message, session: AsyncSession) -> None:
    classified = ClassifiedIntent(intent=UserIntent.FORECAST)
    await handle_classified_intent(message, session, classified)


@router.message(Command("whatif"))
@router.message(Command("advisor"))
async def cmd_advisor_hint(message: Message) -> None:
    await message.answer(
        "Спроси свободным текстом:\n"
        "• что будет, если 50000 закину на кредитку?\n"
        "• могу ли iPhone за 120000 в следующем месяце?\n"
        "• сколько отложу, если потрачу 100000?\n"
        "• сколько теряю на процентах?"
    )
