from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import transaction_repo, user_repo
from src.services import balance_service

router = Router()

PERIOD_LABELS = {"day": "сегодня", "week": "неделю", "month": "месяц"}


def report_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="report:day"),
                InlineKeyboardButton(text="Неделя", callback_data="report:week"),
                InlineKeyboardButton(text="Месяц", callback_data="report:month"),
            ]
        ]
    )


@router.message(Command("report"))
@router.message(lambda m: m.text and m.text.strip() == "📊 Отчёт")
async def cmd_report(message: Message) -> None:
    await message.answer("Расходы за какой период?", reply_markup=report_keyboard())


@router.callback_query(F.data.startswith("report:"))
async def process_report(callback: CallbackQuery, session: AsyncSession) -> None:
    period = callback.data.split(":")[1]
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    since = transaction_repo.period_start(period)
    totals = await transaction_repo.get_expenses_sum(session, user.id, since)

    if not totals:
        text = f"Расходы за {PERIOD_LABELS[period]}: пока нет записей."
    else:
        lines = [f"Расходы за {PERIOD_LABELS[period]}:"]
        for currency, amount in totals.items():
            lines.append(f"  {balance_service.format_money(amount, currency)}")
        top = await transaction_repo.get_top_categories(session, user.id, since)
        if top:
            lines.append("")
            lines.append("Топ категорий:")
            for name, icon, amount in top:
                lines.append(f"  {icon or ''} {name}: {amount:,.0f}")
        text = "\n".join(lines)

    await callback.message.edit_text(text)
    await callback.answer()
