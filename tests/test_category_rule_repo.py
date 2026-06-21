import pytest

from src.models.category import Category
from src.models.category_rule import CategoryRule
from src.models.user import User
from src.repositories import category_repo, category_rule_repo
from src.services.merchant_categorizer import resolve_merchant_category


@pytest.mark.asyncio
async def test_upsert_and_find_rule(session):
    await category_repo.ensure_system_categories(session)
    food = await category_repo.get_category_by_slug(session, "food")
    user = User(telegram_id=999001, username="tester")
    session.add(user)
    await session.flush()

    await category_rule_repo.upsert_rule(session, user.id, "LIDL", food.id)
    found = await category_rule_repo.find_category_for_merchant(session, user.id, "LIDL 174 NOVI S")
    assert found is not None
    assert found.slug == "food"


@pytest.mark.asyncio
async def test_user_rule_overrides_builtin(session):
    await category_repo.ensure_system_categories(session)
    clothing = await category_repo.get_category_by_slug(session, "clothing")
    user = User(telegram_id=999002, username="tester2")
    session.add(user)
    await session.flush()

    await category_rule_repo.upsert_rule(session, user.id, "LIDL", clothing.id)
    slug = await resolve_merchant_category(session, user.id, "LIDL 174 NOVI S", llm_slug="food")
    assert slug == "clothing"


@pytest.mark.asyncio
async def test_upsert_updates_existing(session):
    await category_repo.ensure_system_categories(session)
    food = await category_repo.get_category_by_slug(session, "food")
    cafe = await category_repo.get_category_by_slug(session, "cafe")
    user = User(telegram_id=999003, username="tester3")
    session.add(user)
    await session.flush()

    await category_rule_repo.upsert_rule(session, user.id, "DM", food.id)
    await category_rule_repo.upsert_rule(session, user.id, "DM", cafe.id)
    found = await category_rule_repo.find_category_for_merchant(session, user.id, "DM STORE")
    assert found.slug == "cafe"
