from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.category import Category

SYSTEM_CATEGORIES = [
    ("food", "Еда", "🍎"),
    ("cafe", "Кафе", "☕"),
    ("delivery", "Доставка", "🛵"),
    ("transport", "Транспорт", "🚌"),
    ("housing", "Жильё", "🏠"),
    ("telecom", "Связь", "📱"),
    ("subscriptions", "Подписки", "📺"),
    ("health", "Здоровье", "💊"),
    ("clothing", "Одежда", "👕"),
    ("travel", "Путешествия", "✈️"),
    ("business", "Бизнес", "💼"),
    ("debt_payment", "Кредиты/долги", "💳"),
    ("other", "Другое", "📦"),
]


async def ensure_system_categories(session: AsyncSession) -> None:
    result = await session.execute(select(Category).where(Category.is_system.is_(True)))
    existing = {c.slug for c in result.scalars().all()}
    for slug, name, icon in SYSTEM_CATEGORIES:
        if slug not in existing:
            session.add(Category(slug=slug, name=name, icon=icon, is_system=True))
    await session.flush()


async def get_category_by_slug(session: AsyncSession, slug: str) -> Category | None:
    result = await session.execute(select(Category).where(Category.slug == slug))
    return result.scalar_one_or_none()


async def list_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category).order_by(Category.slug))
    return list(result.scalars().all())
