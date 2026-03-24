"""Pure field validators for contract dialog inputs.

Each function returns either a normalized value on success or a Russian-language
error string on failure. Callers detect errors with: isinstance(result, str).
Never raises exceptions.
"""
import datetime
import re
from decimal import Decimal, InvalidOperation


_DATE_ERROR = "Неверная дата. Введите дату в формате ДД.ММ.ГГГГ (например, 15.03.2024)"
_PHONE_ERROR = "Неверный формат телефона. Введите номер в формате +7 XXX XXX XX XX"
_EMAIL_ERROR = "Неверный формат email. Введите корректный email (например, user@example.com)"
_AMOUNT_ERROR = "Сумма должна быть положительным числом"
_AGE_MINOR_ERROR = "Арендатор должен быть совершеннолетним (18+ лет на дату договора)"
_AGE_FUTURE_DOB_ERROR = "Дата рождения не может быть позже даты договора"


def validate_date(raw: str) -> datetime.date | str:
    """Accept DD.MM.YYYY (with or without leading zeros). Return date or error string."""
    try:
        return datetime.datetime.strptime(raw.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return _DATE_ERROR


def validate_phone(raw: str) -> str:
    """Accept +7 XXXXXXXXXX (spaces allowed). Return normalized +7XXXXXXXXXX or error string."""
    cleaned = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if re.fullmatch(r'\+7\d{10}', cleaned):
        return cleaned
    return _PHONE_ERROR


def validate_email(raw: str) -> str:
    """Accept standard email. Return lowercased email or error string."""
    stripped = raw.strip().lower()
    if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', stripped):
        return stripped
    return _EMAIL_ERROR


def validate_amount(raw: str) -> Decimal | str:
    """Accept positive numeric string (spaces allowed). Return Decimal or error string."""
    cleaned = raw.replace(" ", "")
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return _AMOUNT_ERROR
    if amount <= 0:
        return _AMOUNT_ERROR
    return amount


def validate_age(date_of_birth: datetime.date, contract_date: datetime.date) -> bool | str:
    """Check tenant is 18+ on contract_date. Return True or error string."""
    if date_of_birth > contract_date:
        return _AGE_FUTURE_DOB_ERROR
    age = contract_date.year - date_of_birth.year - (
        (contract_date.month, contract_date.day) < (date_of_birth.month, date_of_birth.day)
    )
    if age < 18:
        return _AGE_MINOR_ERROR
    return True
