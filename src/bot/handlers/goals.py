from decimal import Decimal, InvalidOperation

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import goals_repo, user_repo

router = Router()


@router.message(Command("goals"))
async def cmd_goals(message: Message, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    goals = await goals_repo.list_goals(session, user.id)
    if not goals:
        await message.answer("Целей нет.\nЗадай подушку: «подушка безопасности 100000 rsd»")
        return
    lines = ["*Цели:*"]
    for g in goals:
        label = "🛡 Подушка" if g.is_emergency_fund else g.name
        lines.append(f"• {label}: {g.current_amount:,.0f} / {g.target_amount:,.0f} {g.currency}")
    await message.answer("\n".join(lines), parse_mode="Markdown")


async def handle_emergency_fund_text(message: Message, session: AsyncSession) -> bool:
    text = (message.text or "").lower()
    if "подушк" not in text and "emergency" not in text:
        return False
    import re
    match = re.search(r"(\d[\d\s]*)", text)
    if not match:
        await message.answer("Укажи сумму: «подушка безопасности 100000 rsd»")
        return True
    amount = Decimal(match.group(1).replace(" ", ""))
    currency = "EUR" if "eur" in text or "евро" in text else "RSD"
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    goal = await goals_repo.upsert_emergency_fund(session, user.id, amount, currency)
    await message.answer(f"Подушка безопасности: {goal.target_amount:,.0f} {goal.currency} ✅")
    return True
