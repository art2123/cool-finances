from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.family_invite import FamilyInvite
from src.models.user import User
from src.repositories import account_repo, transaction_repo


class FamilyError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass
class FamilyMemberInfo:
    telegram_id: int
    display_name: str | None
    status: str  # "active" | "pending"


async def _ensure_invitee_is_clean(session: AsyncSession, invitee: User) -> None:
    accounts = await account_repo.list_accounts(session, invitee.id, active_only=False)
    if accounts:
        raise FamilyError("У пользователя уже есть счета — нельзя добавить в семью.")
    tx_count = await transaction_repo.count_for_user(session, invitee.id)
    if tx_count > 0:
        raise FamilyError("У пользователя уже есть операции — нельзя добавить в семью.")


async def create_invite(session: AsyncSession, owner: User, telegram_id: int) -> FamilyInvite:
    if owner.family_owner_id is not None:
        raise FamilyError("Только основатель семьи может приглашать.")
    if owner.telegram_id == telegram_id:
        raise FamilyError("Нельзя пригласить самого себя.")

    existing = await session.execute(
        select(FamilyInvite).where(
            FamilyInvite.invitee_telegram_id == telegram_id,
            FamilyInvite.owner_user_id == owner.id,
        )
    )
    if existing.scalar_one_or_none():
        raise FamilyError("Этот пользователь уже приглашён.")

    other_invite = await session.execute(
        select(FamilyInvite).where(
            FamilyInvite.invitee_telegram_id == telegram_id,
            FamilyInvite.owner_user_id != owner.id,
        )
    )
    if other_invite.scalar_one_or_none():
        raise FamilyError("Этот пользователь уже приглашён в другую семью.")

    invitee_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    invitee = invitee_result.scalar_one_or_none()
    if invitee:
        if invitee.family_owner_id is not None:
            if invitee.family_owner_id == owner.id:
                raise FamilyError("Пользователь уже в вашей семье.")
            raise FamilyError("Пользователь уже в другой семье.")
        await _ensure_invitee_is_clean(session, invitee)

    invite = FamilyInvite(owner_user_id=owner.id, invitee_telegram_id=telegram_id)
    session.add(invite)
    await session.flush()
    return invite


async def activate_invite_if_any(session: AsyncSession, actor: User) -> User | None:
    if actor.family_owner_id is not None:
        return None

    result = await session.execute(
        select(FamilyInvite).where(FamilyInvite.invitee_telegram_id == actor.telegram_id)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        return None

    owner_result = await session.execute(select(User).where(User.id == invite.owner_user_id))
    owner = owner_result.scalar_one_or_none()
    if not owner:
        return None

    actor.family_owner_id = invite.owner_user_id
    invite.invitee_user_id = actor.id
    await session.flush()
    return owner


async def list_family_members(session: AsyncSession, owner_id: int) -> list[FamilyMemberInfo]:
    members: list[FamilyMemberInfo] = []

    dependents = await session.execute(select(User).where(User.family_owner_id == owner_id))
    for user in dependents.scalars().all():
        members.append(
            FamilyMemberInfo(
                telegram_id=user.telegram_id,
                display_name=user.first_name or user.username,
                status="active",
            )
        )

    invites = await session.execute(
        select(FamilyInvite).where(
            FamilyInvite.owner_user_id == owner_id,
            FamilyInvite.invitee_user_id.is_(None),
        )
    )
    for invite in invites.scalars().all():
        members.append(
            FamilyMemberInfo(
                telegram_id=invite.invitee_telegram_id,
                display_name=None,
                status="pending",
            )
        )

    return members


async def remove_member(session: AsyncSession, owner: User, telegram_id: int) -> bool:
    if owner.family_owner_id is not None:
        raise FamilyError("Только основатель семьи может удалять участников.")

    member_result = await session.execute(
        select(User).where(User.telegram_id == telegram_id, User.family_owner_id == owner.id)
    )
    member = member_result.scalar_one_or_none()
    if member:
        member.family_owner_id = None

    invite_result = await session.execute(
        select(FamilyInvite).where(
            FamilyInvite.owner_user_id == owner.id,
            FamilyInvite.invitee_telegram_id == telegram_id,
        )
    )
    had_invite = invite_result.scalar_one_or_none() is not None

    await session.execute(
        delete(FamilyInvite).where(
            FamilyInvite.owner_user_id == owner.id,
            FamilyInvite.invitee_telegram_id == telegram_id,
        )
    )
    await session.flush()
    return member is not None or had_invite
