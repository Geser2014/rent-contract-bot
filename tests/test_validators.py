"""Unit tests for field validators — all pure functions, no I/O."""
import datetime
from decimal import Decimal

import pytest

from validators import validate_age, validate_amount, validate_date, validate_email, validate_phone


class TestValidateDate:
    def test_valid_date_returns_date_object(self):
        result = validate_date("15.03.2024")
        assert result == datetime.date(2024, 3, 15)

    def test_valid_date_single_digit_day_month(self):
        result = validate_date("1.3.2024")
        assert result == datetime.date(2024, 3, 1)

    def test_invalid_day_returns_error_string(self):
        result = validate_date("32.01.2024")
        assert isinstance(result, str)
        assert "ДД.ММ.ГГГГ" in result

    def test_wrong_separator_returns_error_string(self):
        result = validate_date("15-03-2024")
        assert isinstance(result, str)

    def test_alpha_input_returns_error_string(self):
        result = validate_date("abc")
        assert isinstance(result, str)

    def test_empty_string_returns_error_string(self):
        result = validate_date("")
        assert isinstance(result, str)


class TestValidatePhone:
    def test_spaced_format_normalizes_to_no_spaces(self):
        result = validate_phone("+7 999 123 45 67")
        assert result == "+79991234567"

    def test_compact_format_passes_through(self):
        result = validate_phone("+79991234567")
        assert result == "+79991234567"

    def test_8_prefix_returns_error_string(self):
        result = validate_phone("89991234567")
        assert isinstance(result, str)
        assert "+7" in result

    def test_non_russian_country_code_returns_error_string(self):
        result = validate_phone("+1 999 123 45 67")
        assert isinstance(result, str)

    def test_alpha_input_returns_error_string(self):
        result = validate_phone("not-a-phone")
        assert isinstance(result, str)


class TestValidateEmail:
    def test_valid_email_returns_lowercased(self):
        result = validate_email("User@EXAMPLE.COM")
        assert result == "user@example.com"

    def test_valid_lowercase_email_passes_through(self):
        result = validate_email("user@example.com")
        assert result == "user@example.com"

    def test_missing_at_sign_returns_error_string(self):
        result = validate_email("not-an-email")
        assert isinstance(result, str)
        assert "email" in result.lower()

    def test_missing_local_part_returns_error_string(self):
        result = validate_email("@example.com")
        assert isinstance(result, str)

    def test_missing_domain_returns_error_string(self):
        result = validate_email("user@")
        assert isinstance(result, str)


class TestValidateAmount:
    def test_integer_string_returns_decimal(self):
        result = validate_amount("5000")
        assert result == Decimal("5000")

    def test_decimal_string_returns_decimal(self):
        result = validate_amount("5000.50")
        assert result == Decimal("5000.50")

    def test_spaced_digits_strips_spaces(self):
        result = validate_amount("5 000")
        assert result == Decimal("5000")

    def test_zero_returns_error_string(self):
        result = validate_amount("0")
        assert isinstance(result, str)
        assert "положительным" in result

    def test_negative_returns_error_string(self):
        result = validate_amount("-100")
        assert isinstance(result, str)

    def test_alpha_returns_error_string(self):
        result = validate_amount("abc")
        assert isinstance(result, str)


class TestValidateAge:
    def test_exactly_18_returns_true(self):
        contract_date = datetime.date(2024, 6, 15)
        dob = datetime.date(2006, 6, 15)  # exactly 18 on contract date
        result = validate_age(dob, contract_date)
        assert result is True

    def test_over_18_returns_true(self):
        contract_date = datetime.date(2024, 6, 15)
        dob = datetime.date(2000, 1, 1)  # 24 years old
        result = validate_age(dob, contract_date)
        assert result is True

    def test_under_18_returns_error_string(self):
        contract_date = datetime.date(2024, 6, 15)
        dob = datetime.date(2007, 6, 16)  # 17y 364d — not yet 18
        result = validate_age(dob, contract_date)
        assert isinstance(result, str)
        assert "18" in result

    def test_dob_after_contract_date_returns_error_string(self):
        contract_date = datetime.date(2024, 6, 15)
        dob = datetime.date(2025, 1, 1)
        result = validate_age(dob, contract_date)
        assert isinstance(result, str)
