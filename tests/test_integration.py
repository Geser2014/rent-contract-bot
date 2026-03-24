"""Integration tests for Phase 6 error boundaries.

Tests that OCR, PDF generation, and DB failures are caught and produce
user-readable Russian messages without crashing the bot.
"""
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest
from sqlalchemy.exc import IntegrityError
from telegram.ext import ConversationHandler

from bot.handlers.conversation import (
    CONFIRM,
    PASSPORT_PAGE1,
    handle_confirm,
    handle_passport_page2,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_document_update():
    """Build a minimal Update mock for a document message."""
    update = MagicMock()
    doc = MagicMock()
    doc.file_id = "file_id_stub"
    update.message.document = doc
    update.message.reply_text = AsyncMock()
    update.message.chat_id = 123
    return update


def _make_context_with_passport():
    """Build context.user_data with passport_page1 bytes pre-loaded."""
    context = MagicMock()
    context.user_data = {
        "passport_page1": b"fake_bytes_page1",
        "group": "Г39",
        "apartment": "39/1",
        "contract_date": __import__("datetime").date(2024, 3, 15),
        "act_date": __import__("datetime").date(2024, 3, 15),
        "monthly_amount": __import__("decimal").Decimal("50000"),
        "deposit_amount": __import__("decimal").Decimal("100000"),
        "deposit_split": False,
        "tenant_phone": "+79991234567",
        "tenant_email": "tenant@example.com",
    }
    return context


def _make_confirm_update():
    """Build a minimal Update mock for a callback_query 'confirm' press."""
    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "confirm"
    query.message.chat_id = 123
    update.callback_query = query
    return update


def _make_context_with_passport_fields():
    """Build context.user_data with all fields populated including passport_fields."""
    context = MagicMock()
    context.bot.send_document = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {
        "group": "Г39",
        "apartment": "39/1",
        "contract_date": __import__("datetime").date(2024, 3, 15),
        "act_date": __import__("datetime").date(2024, 3, 15),
        "monthly_amount": __import__("decimal").Decimal("50000"),
        "deposit_amount": __import__("decimal").Decimal("100000"),
        "deposit_split": False,
        "tenant_phone": "+79991234567",
        "tenant_email": "tenant@example.com",
        "passport_fields": {
            "tenant_full_name": "Иванов Иван Иванович",
            "tenant_dob": "15.06.1990",
            "tenant_birthplace": "г. Москва",
            "tenant_gender": "М",
            "passport_series": "4510",
            "passport_number": "123456",
            "passport_issued_date": "01.01.2015",
            "passport_issued_by": "УФМС России",
            "passport_division_code": "772-001",
            "tenant_address": "г. Москва, ул. Ленина, д. 1",
        },
    }
    return context


# ---------------------------------------------------------------------------
# OCR error boundary tests
# ---------------------------------------------------------------------------

async def test_ocr_api_error():
    """anthropic.APIError in extract_passport_fields -> PASSPORT_PAGE1, Russian error message."""
    update = _make_document_update()
    context = _make_context_with_passport()

    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake_bytes_p2"))
    context.bot.get_file = AsyncMock(return_value=tg_file)

    with patch(
        "bot.handlers.conversation.ocr_service.extract_passport_fields",
        side_effect=anthropic.APIError(message="network error", request=MagicMock(), body=None),
    ):
        result = await handle_passport_page2(update, context)

    assert result == PASSPORT_PAGE1
    update.message.reply_text.assert_called()
    last_call_text = update.message.reply_text.call_args_list[-1][0][0]
    assert "распознать паспорт" in last_call_text


async def test_ocr_value_error():
    """ValueError from extract_passport_fields (no tool_use block) -> PASSPORT_PAGE1."""
    update = _make_document_update()
    context = _make_context_with_passport()

    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake_bytes_p2"))
    context.bot.get_file = AsyncMock(return_value=tg_file)

    with patch(
        "bot.handlers.conversation.ocr_service.extract_passport_fields",
        side_effect=ValueError("no tool_use block"),
    ):
        result = await handle_passport_page2(update, context)

    assert result == PASSPORT_PAGE1


# ---------------------------------------------------------------------------
# PDF generation error boundary tests
# ---------------------------------------------------------------------------

async def test_pdf_timeout_error():
    """subprocess.TimeoutExpired in generate_contract -> END, timeout message."""
    update = _make_confirm_update()
    context = _make_context_with_passport_fields()

    with patch(
        "bot.handlers.conversation.generate_contract",
        side_effect=subprocess.TimeoutExpired(cmd="libreoffice", timeout=30),
    ):
        result = await handle_confirm(update, context)

    assert result == ConversationHandler.END
    update.callback_query.edit_message_text.assert_called()
    calls = [str(c) for c in update.callback_query.edit_message_text.call_args_list]
    assert any("долго" in c for c in calls)


async def test_pdf_runtime_error():
    """RuntimeError in generate_contract -> END, generic failure message."""
    update = _make_confirm_update()
    context = _make_context_with_passport_fields()

    with patch(
        "bot.handlers.conversation.generate_contract",
        side_effect=RuntimeError("LibreOffice produced no output"),
    ):
        result = await handle_confirm(update, context)

    assert result == ConversationHandler.END
    update.callback_query.edit_message_text.assert_called()
    calls = [str(c) for c in update.callback_query.edit_message_text.call_args_list]
    assert any("Не удалось создать договор" in c for c in calls)


# ---------------------------------------------------------------------------
# Database error boundary tests
# ---------------------------------------------------------------------------

async def test_db_integrity_error():
    """IntegrityError in save_contract (duplicate number) -> END, duplicate message."""
    update = _make_confirm_update()
    context = _make_context_with_passport_fields()

    with (
        patch(
            "bot.handlers.conversation.generate_contract",
            return_value="/tmp/fake.pdf",
        ),
        patch("builtins.open", MagicMock()),
        patch(
            "bot.handlers.conversation.database.save_contract",
            side_effect=IntegrityError("UNIQUE", {}, Exception()),
        ),
    ):
        result = await handle_confirm(update, context)

    assert result == ConversationHandler.END
    context.bot.send_message.assert_called_once()
    msg_text = context.bot.send_message.call_args[1]["text"]
    assert "уже существует" in msg_text


# ---------------------------------------------------------------------------
# Happy path smoke test
# ---------------------------------------------------------------------------

async def test_happy_path_confirm():
    """Full success path: generate_contract + save_contract + send_document all succeed."""
    update = _make_confirm_update()
    context = _make_context_with_passport_fields()

    with (
        patch(
            "bot.handlers.conversation.generate_contract",
            return_value="/tmp/fake_contract.pdf",
        ),
        patch("builtins.open", MagicMock()),
        patch(
            "bot.handlers.conversation.database.save_contract",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await handle_confirm(update, context)

    assert result == ConversationHandler.END
    context.bot.send_document.assert_called_once()
