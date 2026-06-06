from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import main_menu_keyboard
from src.repositories import account_repo, category_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import undo_last_transaction

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await category_repo.ensure_system_categories(session)

    await message.answer(
        f"Привет, {user.first_name or 'друг'}! 👋\n\n"
        "Я твой финансовый помощник.\n\n"
        "*Запись:*\n"
        "• кофе 200 динар / фото чека\n"
        "• зарплата 180000\n\n"
        "*Счета и баланс:*\n"
        "/add_account /balance /accounts /transfer\n\n"
        "*Кредиты:*\n"
        "/debts /interest /credit_terms\n"
        "• что будет, если 50000 закину на кредитку?\n\n"
        "*Прогнозы:*\n"
        "/forecast — план на месяц\n"
        "• могу ли iPhone в следующем месяце?\n"
        "• сколько отложу, если потрачу 100000?\n\n"
        "*Напоминания:*\n"
        "/remind /reminders\n\n"
        "/report /undo /help",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Примеры:\n"
        "• кофе 200 динар\n"
        "• зарплата 180000 на raiffeisen\n"
        "• что будет, если 50к на visa?\n"
        "• могу ли куртку за 80 евро?\n"
        "• напомни за 5 дней до 25-го про аренду 35000\n"
        "• подушка безопасности 100000 rsd\n\n"
        "Команды: /balance /debts /interest /forecast /transfer /set_rate"
    )


@router.message(Command("balance"))
@router.message(lambda m: m.text and m.text.strip() == "💰 Баланс")
@router.message(lambda m: m.text and any(k in m.text.lower() for k in ["сколько на", "на картах", "на счетах"]) and "если" not in m.text.lower())
async def cmd_balance(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    by_currency = await balance_service.get_balances_by_currency(session, user.id)
    debts = await balance_service.get_debt_totals(session, user.id)

    lines = ["*Балансы по счетам:*", balance_service.format_accounts_list(accounts), ""]
    if by_currency:
        lines.append("*Свободные средства:*")
        for cur, total in by_currency.items():
            lines.append(f"  {cur}: {balance_service.format_money(total, cur)}")
    if debts:
        lines.append("")
        lines.append("*Долги:*")
        for cur, total in debts.items():
            lines.append(f"  {cur}: {balance_service.format_money(total, cur)}")

    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("accounts"))
@router.message(lambda m: m.text and m.text.strip() == "💳 Счета")
async def cmd_accounts(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    accounts = await account_repo.list_accounts(session, user.id)
    await message.answer(balance_service.format_accounts_list(accounts))


@router.message(Command("undo"))
@router.message(lambda m: m.text and m.text.strip() == "↩️ Отмена")
async def cmd_undo(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    result = await undo_last_transaction(session, user.id)
    if not result:
        await message.answer("Нет операций для отмены.")
        return
    tx, account = result
    await message.answer(
        f"Отменил операцию #{tx.id}.\n"
        f"Баланс {account.name}: {balance_service.format_money(account.balance, account.currency)}"
    )
