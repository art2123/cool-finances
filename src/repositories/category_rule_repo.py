from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.category import Category
from src.models.category_rule import CategoryRule


async def find_category_for_merchant(
    session: AsyncSession,
    user_id: int,
    merchant: str,
) -> Category | None:
    if not merchant.strip():
        return None
    upper = merchant.upper()
    result = await session.execute(
        select(CategoryRule, Category)
        .join(Category, CategoryRule.category_id == Category.id)
        .where(CategoryRule.user_id == user_id)
        .order_by(CategoryRule.priority.desc(), CategoryRule.id.desc())
    )
    for rule, category in result.all():
        pattern = rule.pattern.upper()
        if pattern in upper:
            return category
    return None


async def upsert_rule(
    session: AsyncSession,
    user_id: int,
    pattern: str,
    category_id: int,
    *,
    priority: int = 10,
) -> CategoryRule:
    pattern = pattern.strip().upper()
    result = await session.execute(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id,
            CategoryRule.pattern == pattern,
        )
    )
    rule = result.scalar_one_or_none()
    if rule:
        rule.category_id = category_id
        rule.priority = priority
    else:
        rule = CategoryRule(
            user_id=user_id,
            pattern=pattern,
            category_id=category_id,
            priority=priority,
        )
        session.add(rule)
    await session.flush()
    return rule
