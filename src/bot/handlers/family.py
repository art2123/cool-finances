from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import family_repo, user_repo
from src.repositories.family_repo import FamilyError

router = Router()


def _format_members_list(members: list[family_repo.FamilyMemberInfo]) -> str:
    if not members:
        return "Пока никого нет. Добавь: /family_add <telegram_id>"

    lines = ["*Участники семьи:*"]
    for member in members:
        name = member.display_name or "—"
        if member.status == "active":
            lines.append(f"• {name} (`{member.telegram_id}`) — активен")
        else:
            lines.append(f"• `{member.telegram_id}` — ожидает входа в бота")
    return "\n".join(lines)


async def _add_family_member(message: Message, session: AsyncSession, telegram_id: int) -> None:
    owner = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        resolve_family=False,
    )
    try:
        await family_repo.create_invite(session, owner, telegram_id)
        await message.answer(
            f"Приглашение создано для ID `{telegram_id}`.\n"
            "Когда человек откроет бота, он подключится к вашему бюджету.",
            parse_mode="Markdown",
        )
    except FamilyError as e:
        await message.answer(e.message)


@router.message(Command("family"))
async def cmd_family(message: Message, session: AsyncSession) -> None:
    actor = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        resolve_family=False,
    )

    if actor.family_owner_id:
        owner = await user_repo.get_user_by_id(session, actor.family_owner_id)
        owner_name = (owner.first_name or owner.username or "основателя") if owner else "основателя"
        await message.answer(f"Вы в семейном бюджете *{owner_name}*.", parse_mode="Markdown")
        return

    members = await family_repo.list_family_members(session, actor.id)
    text = _format_members_list(members)
    text += (
        "\n\n*Управление:*\n"
        "/family_add <telegram_id> — пригласить\n"
        "/family_remove <telegram_id> — удалить\n"
        "Или перешли сообщение человека с командой /family_add"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("family_add"), F.forward_from)
async def cmd_family_add_forward(message: Message, session: AsyncSession) -> None:
    if not message.forward_from:
        return
    await _add_family_member(message, session, message.forward_from.id)


@router.message(Command("family_add"))
async def cmd_family_add(message: Message, session: AsyncSession) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Использование: /family_add <telegram_id>\n"
            "Или перешли сообщение человека вместе с командой /family_add"
        )
        return

    try:
        telegram_id = int(parts[1].strip())
    except ValueError:
        await message.answer("Укажи числовой Telegram ID.")
        return

    await _add_family_member(message, session, telegram_id)


@router.message(Command("family_remove"))
async def cmd_family_remove(message: Message, session: AsyncSession) -> None:
    owner = await user_repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        resolve_family=False,
    )

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /family_remove <telegram_id>")
        return

    try:
        telegram_id = int(parts[1].strip())
    except ValueError:
        await message.answer("Укажи числовой Telegram ID.")
        return

    try:
        removed = await family_repo.remove_member(session, owner, telegram_id)
    except FamilyError as e:
        await message.answer(e.message)
        return

    if removed:
        await message.answer(f"Участник `{telegram_id}` удалён из семьи.", parse_mode="Markdown")
    else:
        await message.answer("Участник с таким ID не найден.")
