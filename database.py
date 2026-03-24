"""Async database layer — SQLAlchemy 2.0 + aiosqlite.

Usage:
    await database.init()                    # create tables (idempotent)
    row_id = await database.save_contract(contract_data)
"""
import datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import config
from logger import get_logger
from models import Base, Contract, ContractData

_log = get_logger(__name__)

# Module-level engine — created once, reused across calls.
# Tests override this by calling _configure(url) before init().
_engine = create_async_engine(
    f"sqlite+aiosqlite:///{config.DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)
_AsyncSession = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def _configure(url: str) -> None:
    """Override engine URL — used by tests to inject an in-memory database."""
    global _engine, _AsyncSession  # noqa: PLW0603
    _engine = create_async_engine(url, echo=False)
    _AsyncSession = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def init() -> None:
    """Create all tables defined in Base.metadata. Safe to call multiple times."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _log.info("Database initialized: %s", config.DB_PATH)


async def save_contract(data: ContractData) -> int:
    """Insert a ContractData record. Returns the new row id."""
    async with _AsyncSession() as session:
        async with session.begin():
            row = Contract(
                contract_number=data.contract_number,
                group=data.group,
                apartment=data.apartment,
                tenant_full_name=data.tenant_full_name,
                tenant_dob=data.tenant_dob,
                tenant_birthplace=data.tenant_birthplace,
                tenant_gender=data.tenant_gender,
                tenant_address=data.tenant_address,
                passport_series=data.passport_series,
                passport_number=data.passport_number,
                passport_issued_date=data.passport_issued_date,
                passport_issued_by=data.passport_issued_by,
                passport_division_code=data.passport_division_code,
                tenant_phone=data.tenant_phone,
                tenant_email=data.tenant_email,
                contract_date=data.contract_date,
                act_date=data.act_date,
                monthly_amount=data.monthly_amount,
                deposit_amount=data.deposit_amount,
                deposit_split=data.deposit_split,
                pdf_path=data.pdf_path,
                created_at=datetime.datetime.now(datetime.UTC),
            )
            session.add(row)
        await session.refresh(row)
        _log.info("Contract saved: %s (id=%d)", data.contract_number, row.id)
        return row.id
