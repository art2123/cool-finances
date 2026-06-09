from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.parsers.intent_classifier import classify_intent
from src.parsers.reminder_parser import parse_reminder_text
from src.repositories import account_repo, reminder_repo, user_repo
from src.services.reminder_service import create_from_draft, format_reminders_list

router = Router()


@router.message(Command("reminders"))
async def cmd_reminders(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    reminders = await reminder_repo.list_reminders(session, user.id)
    await message.answer(format_reminders_list(reminders), parse_mode="Markdown")


@router.message(Command("remind"))
async def cmd_remind_hint(message: Message) -> None:
    await message.answer(
        "Примеры:\n"
        "• напомни за 5 дней до 25-го платить за квартиру 35000\n"
        "• напоминай про налоги 15-го каждого квартала\n"
        "• 🔔 Напоминания — список"
    )


async def handle_reminder_intent(message: Message, session: AsyncSession) -> bool:
    from src.domain.enums import UserIntent

    classified = classify_intent(message.text or "")
    if classified.intent != UserIntent.REMINDER:
        return False

    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    draft = parse_reminder_text(message.text or "")
    accounts = await account_repo.list_accounts(session, user.id)
    account_id = accounts[0].id if len(accounts) == 1 else None

    reminder = await create_from_draft(session, user.id, draft, account_id)
    await message.answer(
        f"Напоминание создано ✅\n"
        f"{reminder.title}"
        + (f" — {reminder.amount:,.0f} {reminder.currency}" if reminder.amount else "")
        + f"\nСледующее: {reminder.next_remind_at.strftime('%d.%m.%Y %H:%M')}",
        parse_mode="Markdown",
    )
    return True
