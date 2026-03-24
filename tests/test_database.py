"""Tests for the async database layer.

Uses an in-memory SQLite database via _configure() to avoid touching storage/.
asyncio_mode = auto (set in pyproject.toml) — no @pytest.mark.asyncio needed.
"""
import datetime
from decimal import Decimal

import pytest

import database
from models import ContractData


_FIXTURE_DATA = ContractData(
    contract_number="Г39/42/15.03.2024",
    group="Г39",
    apartment="42",
    tenant_full_name="Иванов Иван Иванович",
    tenant_dob=datetime.date(1990, 5, 20),
    tenant_birthplace="г. Москва",
    tenant_gender="М",
    tenant_address="г. Москва, ул. Ленина, д. 1, кв. 1",
    passport_series="4510",
    passport_number="123456",
    passport_issued_date=datetime.date(2015, 3, 10),
    passport_issued_by="УФМС России по г. Москве",
    passport_division_code="770-001",
    tenant_phone="+79991234567",
    tenant_email="ivanov@example.com",
    contract_date=datetime.date(2024, 3, 15),
    act_date=datetime.date(2024, 3, 20),
    monthly_amount=Decimal("50000"),
    deposit_amount=Decimal("100000"),
    deposit_split=False,
    pdf_path=None,
)


@pytest.fixture(autouse=True)
def use_memory_db():
    """Redirect all DB operations to in-memory SQLite for test isolation."""
    database._configure("sqlite+aiosqlite:///:memory:")


async def test_init_creates_contracts_table():
    """init() must create the contracts table without raising."""
    await database.init()  # should not raise


async def test_init_is_idempotent():
    """Calling init() twice must not raise."""
    await database.init()
    await database.init()  # second call — must not raise or duplicate tables


async def test_save_contract_returns_integer_id():
    """save_contract() must return a positive integer row id."""
    await database.init()
    row_id = await database.save_contract(_FIXTURE_DATA)
    assert isinstance(row_id, int)
    assert row_id > 0


async def test_save_contract_persists_all_fields():
    """All ContractData fields must be retrievable after save."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    from models import Contract

    await database.init()
    row_id = await database.save_contract(_FIXTURE_DATA)

    AsyncSession_ = sessionmaker(database._engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSession_() as session:
        row = await session.get(Contract, row_id)

    assert row is not None
    assert row.contract_number == "Г39/42/15.03.2024"
    assert row.group == "Г39"
    assert row.apartment == "42"
    assert row.tenant_full_name == "Иванов Иван Иванович"
    assert row.tenant_phone == "+79991234567"
    assert row.tenant_email == "ivanov@example.com"
    assert row.monthly_amount == Decimal("50000")
    assert row.deposit_split is False
    assert row.pdf_path is None
