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
    patches = [
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counter_amount NUMERIC(18, 2)",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counter_currency TEXT",
        "ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'conversion'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS family_owner_id INTEGER REFERENCES users(id)",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS actor_user_id INTEGER REFERENCES users(id)",
        """
            CREATE TABLE IF NOT EXISTS family_invites (
                id SERIAL PRIMARY KEY,
                owner_user_id INTEGER NOT NULL REFERENCES users(id),
                invitee_telegram_id BIGINT NOT NULL,
                invitee_user_id INTEGER REFERENCES users(id),
                created_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE (owner_user_id, invitee_telegram_id)
            )
        """,
    ]
    for patch in patches:
        try:
            await conn.execute(text(patch))
        except Exception:
            continue


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await _apply_schema_patches(conn)
        except Exception:
            # SQLite / старые инстансы без enum-типа — create_all достаточно
            pass
