from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.merchant_patterns import match_builtin_category
from src.repositories import category_rule_repo


async def resolve_merchant_category(
    session: AsyncSession,
    user_id: int,
    merchant: str | None,
    llm_slug: str | None = None,
) -> str | None:
    if merchant:
        user_category = await category_rule_repo.find_category_for_merchant(session, user_id, merchant)
        if user_category:
            return user_category.slug

        builtin = match_builtin_category(merchant)
        if builtin:
            return builtin

    if llm_slug:
        return llm_slug

    return None
