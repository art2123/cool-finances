import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import Base
from src.domain.enums import AccountType
from src.models.account import Account
from src.models.family_invite import FamilyInvite
from src.models.transaction import Transaction
from src.models.user import User
from src.repositories import account_repo, transaction_repo
from src.services.transaction_service import record_conversion, record_expense, update_transaction


_TEST_TABLES = [
    User.__table__,
    FamilyInvite.__table__,
    Account.__table__,
    Transaction.__table__,
]


async def _create_user(session: AsyncSession, telegram_id: int) -> User:
    user = User(telegram_id=telegram_id, first_name="Test")
    session.add(user)
    await session.flush()
    return user


async def _run_with_session(func) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_TEST_TABLES))

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await func(session)

    await engine.dispose()


def test_update_expense_amount_recomputes_balance() -> None:
    async def scenario(session: AsyncSession) -> None:
        user = await _create_user(session, 100)
        account = await account_repo.create_account(
            session,
            user_id=user.id,
            name="Card",
            currency="RSD",
            balance=Decimal("1000"),
            account_type=AccountType.DEBIT,
        )
        tx, account = await record_expense(session, user.id, account.id, Decimal("200"), "RSD")
        assert account.balance == Decimal("800")

        updated = await update_transaction(session, user.id, tx.id, amount=Decimal("300"))

        assert updated.amount == Decimal("300")
        assert account.balance == Decimal("700")

    asyncio.run(_run_with_session(scenario))


def test_update_conversion_fields_recomputes_both_accounts() -> None:
    async def scenario(session: AsyncSession) -> None:
        user = await _create_user(session, 200)
        from_acc = await account_repo.create_account(
            session,
            user_id=user.id,
            name="RSD Card",
            currency="RSD",
            balance=Decimal("10000"),
            account_type=AccountType.DEBIT,
        )
        to_acc = await account_repo.create_account(
            session,
            user_id=user.id,
            name="EUR Card",
            currency="EUR",
            balance=Decimal("100"),
            account_type=AccountType.DEBIT,
        )
        tx, from_acc, to_acc = await record_conversion(
            session,
            user.id,
            from_acc.id,
            to_acc.id,
            Decimal("1000"),
            Decimal("10"),
        )
        assert from_acc.balance == Decimal("9000")
        assert to_acc.balance == Decimal("110")

        new_from = await account_repo.create_account(
            session,
            user_id=user.id,
            name="New RSD Card",
            currency="RSD",
            balance=Decimal("5000"),
            account_type=AccountType.DEBIT,
        )
        new_to = await account_repo.create_account(
            session,
            user_id=user.id,
            name="New EUR Card",
            currency="EUR",
            balance=Decimal("50"),
            account_type=AccountType.DEBIT,
        )

        updated = await update_transaction(
            session,
            user.id,
            tx.id,
            amount=Decimal("1500"),
            counter_amount=Decimal("15"),
            account_id=new_from.id,
            counter_account_id=new_to.id,
        )

        assert updated.amount == Decimal("1500")
        assert updated.counter_amount == Decimal("15")
        assert from_acc.balance == Decimal("10000")
        assert to_acc.balance == Decimal("100")
        assert new_from.balance == Decimal("3500")
        assert new_to.balance == Decimal("65")

    asyncio.run(_run_with_session(scenario))


def test_update_foreign_expense_sets_settlement_balance() -> None:
    async def scenario(session: AsyncSession) -> None:
        user = await _create_user(session, 300)
        account = await account_repo.create_account(
            session,
            user_id=user.id,
            name="KZT Card",
            currency="KZT",
            balance=Decimal("5000"),
            account_type=AccountType.DEBIT,
        )
        tx, account = await record_expense(
            session,
            user.id,
            account.id,
            Decimal("200"),
            "RSD",
            settlement_amount=Decimal("1680"),
            settlement_currency="KZT",
        )
        assert account.balance == Decimal("3320")

        updated = await update_transaction(
            session,
            user.id,
            tx.id,
            account_id=account.id,
            counter_amount=Decimal("1700"),
        )

        assert updated.counter_amount == Decimal("1700")
        assert account.balance == Decimal("3300")
        reloaded = await transaction_repo.get_transaction_by_id(session, user.id, tx.id)
        assert reloaded is not None
        assert reloaded.counter_amount == Decimal("1700")

    asyncio.run(_run_with_session(scenario))
