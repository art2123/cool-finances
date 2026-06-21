import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import Base
from src.models.account import Account
from src.models.category import Category
from src.models.category_rule import CategoryRule
from src.models.family_invite import FamilyInvite
from src.models.transaction import Transaction
from src.models.user import User

_TEST_TABLES = [
    User.__table__,
    FamilyInvite.__table__,
    Category.__table__,
    CategoryRule.__table__,
    Account.__table__,
    Transaction.__table__,
]


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TEST_TABLES))

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session

    await engine.dispose()
