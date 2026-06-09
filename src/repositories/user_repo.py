from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.repositories import family_repo


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


def format_user_display_name(user: User | None) -> str:
    if not user:
        return "Без автора"
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return f"ID {user.telegram_id}"


async def resolve_data_and_actor(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> tuple[User, User]:
    actor = await get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        resolve_family=False,
    )
    data_user = await get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
    )
    return data_user, actor


async def get_family_telegram_ids(session: AsyncSession, owner_user_id: int) -> list[int]:
    owner = await get_user_by_id(session, owner_user_id)
    if not owner:
        return []

    ids = [owner.telegram_id]
    result = await session.execute(
        select(User.telegram_id).where(User.family_owner_id == owner_user_id)
    )
    ids.extend(row[0] for row in result.all())
    return ids


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    *,
    resolve_family: bool = True,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        if username and user.username != username:
            user.username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
    else:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.flush()

    if not resolve_family:
        return user

    if user.family_owner_id is not None:
        owner = await get_user_by_id(session, user.family_owner_id)
        if owner:
            return owner

    activated_owner = await family_repo.activate_invite_if_any(session, user)
    if activated_owner:
        return activated_owner

    return user
