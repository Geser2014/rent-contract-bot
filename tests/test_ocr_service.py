"""Tests for ocr_service.py — OCR-03, OCR-04, OCR-05.

Run: python -m pytest tests/test_ocr_service.py -x -q

No real API calls are made. extract_passport_fields is tested with
a mocked AsyncAnthropic client. Pillow resize is tested with synthetic images.
"""
import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from ocr_service import (
    PASSPORT_FIELDS,
    _resize_image_bytes,
    extract_passport_fields,
    format_ocr_summary,
    get_unclear_fields,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def make_all_clear_fields() -> dict[str, str]:
    """Return a dict with all 10 passport fields set to non-UNCLEAR values."""
    return {
        "tenant_full_name": "Иванов Иван Иванович",
        "tenant_dob": "15.03.1990",
        "tenant_birthplace": "г. Москва",
        "tenant_gender": "М",
        "passport_series": "1234",
        "passport_number": "567890",
        "passport_issued_date": "01.01.2010",
        "passport_issued_by": "МВД России по г. Москве",
        "passport_division_code": "123-456",
        "tenant_address": "г. Москва, ул. Ленина, д. 1, кв. 1",
    }


def make_test_jpeg(width: int, height: int) -> bytes:
    """Create a synthetic JPEG in-memory using Pillow."""
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# class TestGetUnclearFields
# ---------------------------------------------------------------------------

class TestGetUnclearFields:
    def test_all_unclear(self):
        """All 10 fields set to 'UNCLEAR' → returns all 10 PASSPORT_FIELDS names."""
        fields = {k: "UNCLEAR" for k in PASSPORT_FIELDS}
        result = get_unclear_fields(fields)
        assert result == PASSPORT_FIELDS

    def test_none_unclear(self):
        """No UNCLEAR values → returns empty list."""
        result = get_unclear_fields(make_all_clear_fields())
        assert result == []

    def test_mixed(self):
        """Only the UNCLEAR fields are returned, in PASSPORT_FIELDS order."""
        fields = make_all_clear_fields()
        fields["tenant_full_name"] = "UNCLEAR"
        fields["tenant_address"] = "UNCLEAR"
        result = get_unclear_fields(fields)
        assert result == ["tenant_full_name", "tenant_address"]

    def test_case_insensitive(self):
        """Lowercase 'unclear' is still treated as UNCLEAR."""
        fields = make_all_clear_fields()
        fields["tenant_full_name"] = "unclear"
        result = get_unclear_fields(fields)
        assert "tenant_full_name" in result

    def test_whitespace_stripped(self):
        """Padded '  UNCLEAR  ' is still treated as UNCLEAR after strip."""
        fields = make_all_clear_fields()
        fields["tenant_full_name"] = "  UNCLEAR  "
        result = get_unclear_fields(fields)
        assert "tenant_full_name" in result


# ---------------------------------------------------------------------------
# class TestFormatOcrSummary
# ---------------------------------------------------------------------------

class TestFormatOcrSummary:
    def test_contains_all_russian_labels(self):
        """All 10 Russian labels must appear in the formatted output."""
        result = format_ocr_summary(make_all_clear_fields())
        expected_labels = [
            "ФИО",
            "Дата рождения",
            "Место рождения",
            "Пол",
            "Серия",
            "Номер",
            "Дата выдачи",
            "Кем выдан",
            "Код подразделения",
            "Адрес регистрации",
        ]
        for label in expected_labels:
            assert label in result, f"Russian label '{label}' not found in summary"

    def test_unclear_field_marked(self):
        """An UNCLEAR field value is suffixed with ⚠️ UNCLEAR in the output."""
        fields = make_all_clear_fields()
        fields["tenant_full_name"] = "UNCLEAR"
        result = format_ocr_summary(fields)
        assert "⚠️ UNCLEAR" in result

    def test_clear_field_not_marked(self):
        """No warning marker appears when all fields are clear."""
        result = format_ocr_summary(make_all_clear_fields())
        assert "⚠️ UNCLEAR" not in result

    def test_header_present(self):
        """The formatted output contains the header 'Данные паспорта'."""
        result = format_ocr_summary(make_all_clear_fields())
        assert "Данные паспорта" in result


# ---------------------------------------------------------------------------
# class TestResizeImageBytes
# ---------------------------------------------------------------------------

class TestResizeImageBytes:
    def test_large_image_resized(self):
        """3200x2400 image → longest edge <= 1600 after resize."""
        raw = make_test_jpeg(3200, 2400)
        result = _resize_image_bytes(raw)
        img = Image.open(io.BytesIO(result))
        assert max(img.width, img.height) <= 1600

    def test_small_image_unchanged_dimensions(self):
        """800x600 image → no upscaling; longest edge stays <= 800."""
        raw = make_test_jpeg(800, 600)
        result = _resize_image_bytes(raw)
        img = Image.open(io.BytesIO(result))
        assert max(img.width, img.height) <= 800

    def test_returns_jpeg_bytes(self):
        """Result is valid JPEG bytes regardless of input dimensions."""
        raw = make_test_jpeg(100, 100)
        result = _resize_image_bytes(raw)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"


# ---------------------------------------------------------------------------
# class TestExtractPassportFields
# ---------------------------------------------------------------------------

def _make_mock_response(fields: dict) -> MagicMock:
    """Build a mock Anthropic response with a valid tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "extract_passport_fields"
    tool_block.input = fields
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.usage.input_tokens = 150
    response.usage.output_tokens = 60
    response.content = [tool_block]
    return response


class TestExtractPassportFields:
    async def test_returns_correct_fields(self):
        """Mocked _CLIENT returns the expected 10-field dict unchanged."""
        expected = make_all_clear_fields()
        with patch("ocr_service._CLIENT") as mock_client:
            mock_client.messages.create = AsyncMock(
                return_value=_make_mock_response(expected)
            )
            result = await extract_passport_fields(
                make_test_jpeg(100, 100),
                make_test_jpeg(100, 100),
            )
        assert result == expected

    async def test_raises_on_no_tool_use_block(self):
        """ValueError is raised when Claude response contains no tool_use block."""
        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = []
        with patch("ocr_service._CLIENT") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=response)
            with pytest.raises(ValueError):
                await extract_passport_fields(
                    make_test_jpeg(100, 100),
                    make_test_jpeg(100, 100),
                )

    async def test_messages_create_called_once(self):
        """Claude API is called exactly once per extract_passport_fields call."""
        expected = make_all_clear_fields()
        with patch("ocr_service._CLIENT") as mock_client:
            mock_client.messages.create = AsyncMock(
                return_value=_make_mock_response(expected)
            )
            await extract_passport_fields(
                make_test_jpeg(100, 100),
                make_test_jpeg(100, 100),
            )
            assert mock_client.messages.create.call_count == 1
