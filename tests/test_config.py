import pytest

from src.core.config import Settings, validate_production_config


def test_validate_production_config_rejects_local_redis_with_webhook() -> None:
    settings = Settings(
        webhook_url="https://app.example.com",
        redis_url="redis://localhost:6379/0",
    )
    with pytest.raises(RuntimeError, match="REDIS_URL points to localhost"):
        validate_production_config(settings)


def test_validate_production_config_allows_local_redis_without_webhook() -> None:
    settings = Settings(redis_url="redis://localhost:6379/0")
    validate_production_config(settings)


def test_validate_production_config_allows_railway_redis() -> None:
    settings = Settings(
        webhook_url="https://app.example.com",
        redis_url="redis://default:pass@redis.railway.internal:6379",
    )
    validate_production_config(settings)
