"""Unit tests for bot/handlers/conversation.py state handlers.

Tests cover state transition logic using mocked Telegram objects.
No real Telegram connection required — all Update and Context objects are mocked.
asyncio_mode=auto (pyproject.toml) — no @pytest.mark.asyncio decorators.
"""
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.conversation import (
    APARTMENT,
    APARTMENTS,
    CONTRACT_DATE,
    ACT_DATE,
    CONFIRM,
    DEPOSIT_AMOUNT,
    DEPOSIT_METHOD,
    EMAIL,
    GROUP,
    MONTHLY_AMOUNT,
    PASSPORT_PAGE1,
    PASSPORT_PAGE2,
    PHONE,
    cmd_cancel,
    cmd_start,
    handle_apartment,
    handle_contract_date,
    handle_group,
    handle_monthly_amount,
    handle_passport_photo_warning_p1,
    handle_passport_photo_warning_p2,
    handle_phone,
    handle_unexpected,
)
from telegram.ext import ConversationHandler


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_text_update(text: str):
    """Create a mock Update with a text message."""
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def make_callback_update(data: str):
    """Create a mock Update with a callback query."""
    update = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def make_context(user_data=None):
    """Create a mock Context with a writable user_data dict."""
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# Tests: /cancel
# ---------------------------------------------------------------------------

async def test_cmd_cancel_clears_user_data_and_ends():
    """cmd_cancel must clear all user_data and return ConversationHandler.END."""
    update = make_text_update("/cancel")
    ctx = make_context(user_data={"group": "Г39", "contract_date": datetime.date(2024, 3, 15)})
    result = await cmd_cancel(update, ctx)
    assert result == ConversationHandler.END
    assert ctx.user_data == {}  # cleared via .clear()


# ---------------------------------------------------------------------------
# Tests: /start
# ---------------------------------------------------------------------------

async def test_cmd_start_returns_group_state():
    """cmd_start sends an inline keyboard message and returns GROUP (0)."""
    update = make_text_update("/start")
    ctx = make_context()
    result = await cmd_start(update, ctx)
    assert result == GROUP
    update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: handle_group
# ---------------------------------------------------------------------------

async def test_handle_group_stores_group_and_returns_apartment():
    """handle_group stores selected group in user_data and returns APARTMENT (1)."""
    update = make_callback_update("Г39")
    ctx = make_context()
    result = await handle_group(update, ctx)
    assert result == APARTMENT
    assert ctx.user_data["group"] == "Г39"
    update.callback_query.answer.assert_called_once()
    update.callback_query.edit_message_text.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: handle_contract_date
# ---------------------------------------------------------------------------

async def test_handle_contract_date_valid():
    """Valid date '15.03.2024' is stored as datetime.date and returns ACT_DATE (3)."""
    update = make_text_update("15.03.2024")
    ctx = make_context()
    result = await handle_contract_date(update, ctx)
    assert result == ACT_DATE
    assert ctx.user_data["contract_date"] == datetime.date(2024, 3, 15)
    update.message.reply_text.assert_called_once()  # advance prompt sent


async def test_handle_contract_date_invalid():
    """Invalid date 'not-a-date' replies with error text and stays in CONTRACT_DATE (2)."""
    update = make_text_update("not-a-date")
    ctx = make_context()
    result = await handle_contract_date(update, ctx)
    assert result == CONTRACT_DATE  # stays in same state
    assert "contract_date" not in ctx.user_data  # not stored
    update.message.reply_text.assert_called_once()  # error message sent


# ---------------------------------------------------------------------------
# Tests: handle_monthly_amount
# ---------------------------------------------------------------------------

async def test_handle_monthly_amount_valid():
    """Valid amount '50000' is stored as Decimal and returns DEPOSIT_AMOUNT (5)."""
    update = make_text_update("50000")
    ctx = make_context()
    result = await handle_monthly_amount(update, ctx)
    assert result == DEPOSIT_AMOUNT
    assert ctx.user_data["monthly_amount"] == Decimal("50000")
    update.message.reply_text.assert_called_once()


async def test_handle_monthly_amount_invalid():
    """Negative amount '-100' replies with error and stays in MONTHLY_AMOUNT (4)."""
    update = make_text_update("-100")
    ctx = make_context()
    result = await handle_monthly_amount(update, ctx)
    assert result == MONTHLY_AMOUNT
    assert "monthly_amount" not in ctx.user_data
    update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: handle_phone
# ---------------------------------------------------------------------------

async def test_handle_phone_valid():
    """Valid phone '+7 999 123 45 67' is stored normalized and returns EMAIL (8)."""
    update = make_text_update("+7 999 123 45 67")
    ctx = make_context()
    result = await handle_phone(update, ctx)
    assert result == EMAIL
    assert ctx.user_data["tenant_phone"] == "+79991234567"
    update.message.reply_text.assert_called_once()


async def test_handle_phone_invalid():
    """Short invalid phone '123' replies with error and stays in PHONE (7)."""
    update = make_text_update("123")
    ctx = make_context()
    result = await handle_phone(update, ctx)
    assert result == PHONE
    assert "tenant_phone" not in ctx.user_data
    update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: passport photo warning handlers
# ---------------------------------------------------------------------------

async def test_handle_passport_photo_warning_p1():
    """Photo message in PASSPORT_PAGE1 returns PASSPORT_PAGE1 (9) with a warning."""
    update = make_text_update("")  # text doesn't matter for photo handlers
    update.message.reply_text = AsyncMock()
    ctx = make_context()
    result = await handle_passport_photo_warning_p1(update, ctx)
    assert result == PASSPORT_PAGE1
    update.message.reply_text.assert_called_once()


async def test_handle_passport_photo_warning_p2():
    """Photo message in PASSPORT_PAGE2 returns PASSPORT_PAGE2 (10) with a warning."""
    update = make_text_update("")
    update.message.reply_text = AsyncMock()
    ctx = make_context()
    result = await handle_passport_photo_warning_p2(update, ctx)
    assert result == PASSPORT_PAGE2
    update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: handle_unexpected
# ---------------------------------------------------------------------------

async def test_handle_unexpected_returns_none():
    """Unexpected message returns None (stays in current state without advancing)."""
    update = make_text_update("garbage input")
    ctx = make_context()
    result = await handle_unexpected(update, ctx)
    assert result is None
    update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: APARTMENTS structure
# ---------------------------------------------------------------------------

def test_apartments_dict_structure():
    """APARTMENTS has 'Г39' with 7 entries and 'Г38' with 8 entries."""
    assert "Г39" in APARTMENTS
    assert "Г38" in APARTMENTS
    assert len(APARTMENTS["Г39"]) == 7
    assert len(APARTMENTS["Г38"]) == 8
    # All apartment IDs start with their group prefix digit
    assert all(apt.startswith("39") for apt in APARTMENTS["Г39"])
    assert all(apt.startswith("38") for apt in APARTMENTS["Г38"])
