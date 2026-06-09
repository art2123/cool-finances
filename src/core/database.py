from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _apply_schema_patches(conn) -> None:
    await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counter_amount NUMERIC(18, 2)"))
    await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counter_currency TEXT"))
    await conn.execute(
        text("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'conversion'")
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await _apply_schema_patches(conn)
        except Exception:
            # SQLite / старые инстансы без enum-типа — create_all достаточно
            pass
