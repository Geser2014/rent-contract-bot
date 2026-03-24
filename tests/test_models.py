"""Tests for models.py — ContractData dataclass and Contract ORM model.

These tests verify that ContractData and Contract can be constructed
and that all required fields exist.
"""
import datetime
from decimal import Decimal

import pytest


def test_contractdata_can_be_constructed():
    """ContractData can be constructed from fixture data without errors."""
    from models import ContractData

    data = ContractData(
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
    assert data.contract_number == "Г39/42/15.03.2024"
    assert data.group == "Г39"
    assert data.apartment == "42"
    assert data.pdf_path is None
    assert data.deposit_split is False


def test_contractdata_default_values():
    """ContractData has sensible defaults for optional fields."""
    from models import ContractData

    data = ContractData(
        contract_number="Г38/10/01.01.2024",
        group="Г38",
        apartment="10",
        tenant_full_name="Петрова Мария Сергеевна",
        tenant_dob=datetime.date(1985, 7, 15),
        tenant_birthplace="г. Санкт-Петербург",
        tenant_gender="Ж",
        tenant_address="г. Москва, ул. Тверская, д. 5, кв. 10",
        passport_series="4520",
        passport_number="654321",
        passport_issued_date=datetime.date(2010, 6, 1),
        passport_issued_by="УФМС по г. Санкт-Петербургу",
        passport_division_code="780-001",
        tenant_phone="+79997654321",
        tenant_email="petrova@example.com",
        contract_date=datetime.date(2024, 1, 1),
        act_date=datetime.date(2024, 1, 5),
        monthly_amount=Decimal("40000"),
        deposit_amount=Decimal("80000"),
    )
    # Default values
    assert data.deposit_split is False
    assert data.pdf_path is None


def test_contract_orm_class_has_tablename():
    """Contract ORM model has __tablename__ = 'contracts'."""
    from models import Contract

    assert Contract.__tablename__ == "contracts"


def test_contract_orm_class_inherits_base():
    """Contract inherits from Base."""
    from models import Base, Contract

    assert issubclass(Contract, Base)


def test_base_is_declarative():
    """Base is a valid SQLAlchemy DeclarativeBase subclass."""
    from sqlalchemy.orm import DeclarativeBase

    from models import Base

    assert issubclass(Base, DeclarativeBase)
