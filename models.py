"""Data models for the rent contract bot.

ContractData: dataclass used as the data transfer object between layers.
Contract: SQLAlchemy ORM model; maps ContractData to the 'contracts' SQLite table.
"""
import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@dataclass
class ContractData:
    """All fields collected during the contract creation dialog.

    This is the DTO passed between FSM, document generation, and persistence layers.
    Fields are populated incrementally during the dialog; pdf_path is set after generation.
    """
    # Contract metadata
    contract_number: str                        # e.g. "Г39/42/15.03.2024"
    group: str                                  # "Г39" or "Г38"
    apartment: str                              # e.g. "42"

    # Tenant personal data (from passport OCR)
    tenant_full_name: str                       # ФИО
    tenant_dob: datetime.date                   # дата рождения
    tenant_birthplace: str                      # место рождения
    tenant_gender: str                          # "М" or "Ж"
    tenant_address: str                         # адрес регистрации

    # Passport data
    passport_series: str                        # серия (4 digits)
    passport_number: str                        # номер (6 digits)
    passport_issued_date: datetime.date         # дата выдачи
    passport_issued_by: str                     # кем выдан
    passport_division_code: str                 # код подразделения (XXX-XXX)

    # Contact data (from dialog)
    tenant_phone: str                           # normalized +7XXXXXXXXXX
    tenant_email: str

    # Contract terms (from dialog)
    contract_date: datetime.date                # дата договора
    act_date: datetime.date                     # дата Акта приёма-передачи
    monthly_amount: Decimal                     # ежемесячная аренда
    deposit_amount: Decimal                     # депозит
    deposit_split: bool = False                 # True = 50%+50%, False = единовременно

    # Set after document generation
    pdf_path: str | None = None


class Contract(Base):
    """SQLAlchemy ORM model for the 'contracts' table.

    One row per completed contract. Mirrors ContractData fields.
    """
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # Contract metadata
    contract_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    group: Mapped[str] = mapped_column(String(10), nullable=False)
    apartment: Mapped[str] = mapped_column(String(20), nullable=False)

    # Tenant personal data
    tenant_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tenant_dob: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    tenant_birthplace: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_gender: Mapped[str] = mapped_column(String(1), nullable=False)
    tenant_address: Mapped[str] = mapped_column(Text, nullable=False)

    # Passport data
    passport_series: Mapped[str] = mapped_column(String(4), nullable=False)
    passport_number: Mapped[str] = mapped_column(String(6), nullable=False)
    passport_issued_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    passport_issued_by: Mapped[str] = mapped_column(Text, nullable=False)
    passport_division_code: Mapped[str] = mapped_column(String(7), nullable=False)

    # Contact data
    tenant_phone: Mapped[str] = mapped_column(String(12), nullable=False)
    tenant_email: Mapped[str] = mapped_column(String(200), nullable=False)

    # Contract terms
    contract_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    act_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    deposit_split: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Set after document generation
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Contract {self.contract_number}>"
