from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import (
    ALL_MENU_BUTTON_TEXTS,
    main_menu_keyboard,
    more_menu_keyboard,
)
from src.repositories import account_repo, category_repo, user_repo
from src.services import balance_service
from src.services.transaction_service import undo_last_transaction

router = Router()


async def _handle_more_menu_button(message: Message, state: FSMContext, session: AsyncSession, text: str) -> None:
    if text == "◀️ Назад":
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard())
        return
    if text == "📊 Отчёт":
        from src.bot.handlers.reports import cmd_report

        await cmd_report(message)
    elif text == "🔄 Конвертация":
        from src.bot.handlers.conversions import cmd_conversion

        await cmd_conversion(message, state, session)
    elif text == "📉 Долги":
        from src.bot.handlers.credits import cmd_debts

        await cmd_debts(message, session)
    elif text == "📈 Проценты":
        from src.bot.handlers.credits import cmd_interest

        await cmd_interest(message, session)
    elif text == "🔮 Прогноз":
        from src.bot.handlers.advisor import cmd_forecast

        await cmd_forecast(message, session)
    elif text == "🔔 Напоминания":
        from src.bot.handlers.reminders import cmd_reminders

        await cmd_reminders(message, session)
        await message.answer(
            "Создать напоминание — напиши текстом:\n"
            "«напомни за 5 дней до 25-го про аренду 35000»"
        )
    elif text == "🎯 Цели":
        from src.bot.handlers.goals import cmd_goals

        await cmd_goals(message, session)
    elif text == "❓ Помощь":
        await cmd_help(message)


@router.message(F.text.in_(ALL_MENU_BUTTON_TEXTS))
async def handle_main_menu_button(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Кнопки ReplyKeyboard — обрабатываем первыми и сбрасываем FSM."""
    await state.clear()
    text = message.text.strip()

    if text == "📋 Ещё":
        await message.answer("Дополнительно:", reply_markup=more_menu_keyboard())
        return

    if text in {
        "📊 Отчёт",
        "🔄 Конвертация",
        "📉 Долги",
        "📈 Проценты",
        "🔮 Прогноз",
        "🔔 Напоминания",
        "🎯 Цели",
        "❓ Помощь",
        "◀️ Назад",
    }:
        await _handle_more_menu_button(message, state, session, text)
        return

    if text == "💰 Баланс":
        await cmd_balance(message, session)
    elif text == "💳 Счета":
        from src.bot.handlers.accounts import show_accounts_hub

        await show_accounts_hub(message, session)
    elif text in {"↩️ Отмена", "⤴️ Отмена"}:
        await cmd_undo(message, session)
    elif text == "➕ Счёт":
        from src.bot.handlers.accounts import cmd_add_account

        await cmd_add_account(message, state)
    elif text == "💸 Перевод":
        from src.bot.handlers.transfers import cmd_transfer

        await cmd_transfer(message, state, session)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    actor = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        resolve_family=False,
    )
    owner = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await category_repo.ensure_system_categories(session)

    greeting_name = actor.first_name or "друг"
    if actor.family_owner_id:
        owner_name = owner.first_name or owner.username or "основателя"
        intro = (
            f"Привет, {greeting_name}! 👋\n\n"
            f"Вы подключены к семейному бюджету *{owner_name}*.\n"
            "Счета и операции общие — функционал такой же, как у основателя.\n\n"
        )
    else:
        intro = (
            f"Привет, {greeting_name}! 👋\n\n"
            "Я твой финансовый помощник.\n\n"
            "Семейный доступ: /family_add <telegram_id> — пригласить близких к общему бюджету.\n\n"
        )

    await message.answer(
        intro
        + "Пользуйся кнопками ниже или пиши обычным текстом:\n"
        "• кофе 200 динар списали 1680 тенге\n"
        "• зарплата 180000\n"
        "• 🔄 Конвертация — в меню «Ещё»\n\n"
        "Справка — ❓ Помощь в меню «Ещё»",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown" if actor.family_owner_id else None,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "*Главное меню:*\n"
        "💰 Баланс · 💳 Счета · 💸 Перевод · 📋 Ещё · ↩️ Отмена\n\n"
        "*Меню «Ещё»:*\n"
        "📊 Отчёт · 🔄 Конвертация · 📉 Долги · 📈 Проценты\n"
        "🔮 Прогноз · 🔔 Напоминания · 🎯 Цели · ❓ Помощь\n\n"
        "*Счета:*\n"
        "💳 Счета — список, добавление и редактирование (название, валюта, баланс, тип)\n\n"
        "*Трата с иностранной карты:*\n"
        "Покупка в одной валюте, списание в другой.\n"
        "• кофе 200 динар списали 1680 тенге\n"
        "В отчёте — 200 RSD, с карты — 1680 KZT.\n\n"
        "*Конвертация (крипта / обмен):*\n"
        "🔄 Конвертация — не трата и не доход.\n"
        "Укажешь сколько ушло и сколько пришло: 5000 RUB → 25000 KZT.\n\n"
        "*Свободный текст:*\n"
        "• зарплата 180000 · что будет, если 50к на visa?\n"
        "• напомни за 5 дней до 25-го про аренду 35000\n\n"
        "*Семейный доступ:*\n"
        "/family — участники семьи\n"
        "/family_add <telegram_id> — пригласить\n"
        "/family_remove <telegram_id> — удалить",
        parse_mode="Markdown",
    )


@router.message(Command("balance"))
@router.message(
    lambda m: m.text
    and any(k in m.text.lower() for k in ["сколько на", "на картах", "на счетах"])
    and "если" not in m.text.lower()
)
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


@router.message(Command("undo"))
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
