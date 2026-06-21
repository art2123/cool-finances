from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.data.merchant_patterns import extract_merchant_pattern
from src.repositories import category_repo, category_rule_repo
from src.repositories.category_repo import SYSTEM_CATEGORIES


def category_label(slug: str | None) -> str:
    if not slug:
        return "?"
    for cat_slug, name, icon in SYSTEM_CATEGORIES:
        if cat_slug == slug:
            return f"{icon} {name}"
    return slug


def remember_rule_keyboard(pattern: str, category_slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, запомнить",
                    callback_data=f"learn:yes:{pattern}:{category_slug}",
                ),
                InlineKeyboardButton(text="Нет", callback_data="learn:no"),
            ]
        ]
    )


async def offer_remember_rule(message, session, user_id: int, merchant: str | None, category_slug: str) -> bool:
    pattern = extract_merchant_pattern(merchant)
    if not pattern or not category_slug:
        return False
    existing = await category_rule_repo.find_category_for_merchant(session, user_id, pattern)
    if existing and existing.slug == category_slug:
        return False
    label = category_label(category_slug)
    await message.answer(
        f'Запомнить «{pattern}» как {label}?',
        reply_markup=remember_rule_keyboard(pattern, category_slug),
    )
    return True


async def save_learned_rule(session, user_id: int, pattern: str, category_slug: str) -> None:
    category = await category_repo.get_category_by_slug(session, category_slug)
    if not category:
        return
    await category_rule_repo.upsert_rule(session, user_id, pattern, category.id)
