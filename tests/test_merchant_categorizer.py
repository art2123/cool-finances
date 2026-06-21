import pytest

from src.data.merchant_patterns import extract_merchant_pattern, match_builtin_category
from src.repositories import category_repo
from src.services.merchant_categorizer import resolve_merchant_category


def test_lidl_maps_to_food():
    assert match_builtin_category("LIDL 174 NOVI S") == "food"


def test_maxi_maps_to_food():
    assert match_builtin_category("213 - MAXI 217>") == "food"


def test_extract_pattern_lidl():
    assert extract_merchant_pattern("LIDL 174 NOVI S") == "LIDL"


@pytest.mark.asyncio
async def test_builtin_category_resolution(session):
    await category_repo.ensure_system_categories(session)
    slug = await resolve_merchant_category(session, user_id=1, merchant="LIDL 174 NOVI S", llm_slug=None)
    assert slug == "food"


@pytest.mark.asyncio
async def test_llm_slug_fallback(session):
    await category_repo.ensure_system_categories(session)
    slug = await resolve_merchant_category(session, user_id=1, merchant="Unknown Shop XYZ", llm_slug="travel")
    assert slug == "travel"
