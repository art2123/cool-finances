from collections import defaultdict
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import TransactionType
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


async def _format_actor_lines(
    session: AsyncSession,
    rows: list[tuple[int, str, Decimal]],
    indent: str = "  ",
) -> list[str]:
    if not rows:
        return []
    by_actor: dict[int, list[tuple[str, Decimal]]] = defaultdict(list)
    for actor_id, currency, amount in rows:
        by_actor[actor_id].append((currency, amount))

    lines: list[str] = []
    for actor_id, amounts in by_actor.items():
        actor = await user_repo.get_user_by_id(session, actor_id)
        name = user_repo.format_user_display_name(actor)
        parts = [f"{balance_service.format_money(amt, cur)}" for cur, amt in amounts]
        lines.append(f"{indent}{name}: {', '.join(parts)}")
    return lines


async def _format_transfer_actor_lines(
    session: AsyncSession,
    rows: list[tuple[int, str, int, Decimal]],
) -> list[str]:
    if not rows:
        return []
    by_actor: dict[int, list[tuple[str, int, Decimal]]] = defaultdict(list)
    for actor_id, currency, count, amount in rows:
        by_actor[actor_id].append((currency, count, amount))

    lines: list[str] = []
    for actor_id, stats in by_actor.items():
        actor = await user_repo.get_user_by_id(session, actor_id)
        name = user_repo.format_user_display_name(actor)
        parts = []
        for currency, count, amount in stats:
            op_word = "операция" if count == 1 else "операции" if 2 <= count <= 4 else "операций"
            parts.append(f"{count} {op_word} ({balance_service.format_money(amount, currency)})")
        lines.append(f"  {name}: {', '.join(parts)}")
    return lines


async def build_report_text(session: AsyncSession, user_id: int, period: str) -> str:
    since = transaction_repo.period_start(period)
    label = PERIOD_LABELS[period]
    lines: list[str] = []

    totals = await transaction_repo.get_expenses_sum(session, user_id, since)
    if not totals:
        lines.append(f"Расходы за {label}: пока нет записей.")
    else:
        lines.append(f"Расходы за {label}:")
        for currency, amount in totals.items():
            lines.append(f"  {balance_service.format_money(amount, currency)}")
        expense_by_actor = await transaction_repo.get_totals_by_actor(
            session, user_id, since, [TransactionType.EXPENSE]
        )
        actor_lines = await _format_actor_lines(session, expense_by_actor)
        if actor_lines:
            lines.append("")
            lines.append("Кто потратил:")
            lines.extend(actor_lines)
        top = await transaction_repo.get_top_categories(session, user_id, since)
        if top:
            lines.append("")
            lines.append("Топ категорий:")
            for name, icon, amount in top:
                lines.append(f"  {icon or ''} {name}: {amount:,.0f}")

    income_totals = await transaction_repo.get_totals_by_actor(
        session, user_id, since, [TransactionType.INCOME]
    )
    if income_totals:
        lines.append("")
        lines.append(f"Приходы за {label}:")
        income_by_currency: dict[str, Decimal] = defaultdict(Decimal)
        for _, currency, amount in income_totals:
            income_by_currency[currency] += amount
        for currency, amount in income_by_currency.items():
            lines.append(f"  {balance_service.format_money(amount, currency)}")
        actor_lines = await _format_actor_lines(session, income_totals)
        if actor_lines:
            lines.append("Кто внёс:")
            lines.extend(actor_lines)

    transfer_stats = await transaction_repo.get_transfer_stats_by_actor(session, user_id, since)
    if transfer_stats:
        lines.append("")
        lines.append("Переводы и конвертации:")
        lines.extend(await _format_transfer_actor_lines(session, transfer_stats))

    return "\n".join(lines) if lines else f"За {label} записей нет."


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    await message.answer("Расходы за какой период?", reply_markup=report_keyboard())


@router.callback_query(F.data.startswith("report:"))
async def process_report(callback: CallbackQuery, session: AsyncSession) -> None:
    period = callback.data.split(":")[1]
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    text = await build_report_text(session, user.id, period)
    await callback.message.edit_text(text)
    await callback.answer()
