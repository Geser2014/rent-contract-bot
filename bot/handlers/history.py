"""Handler for /history command — list created contracts with pagination."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import database

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def _format_contract_list(contracts, offset: int, total: int) -> str:
    """Format contracts as numbered list."""
    if not contracts:
        return "📋 Договоров пока нет."

    lines = [f"📋 *Договоры* ({offset + 1}–{offset + len(contracts)} из {total}):\n"]
    for i, c in enumerate(contracts, start=offset + 1):
        date_str = c.contract_date.strftime("%d.%m.%Y")
        # Shorten name to last name + initials
        parts = c.tenant_full_name.split()
        if len(parts) >= 3:
            short_name = f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
        elif len(parts) == 2:
            short_name = f"{parts[0]} {parts[1][0]}."
        else:
            short_name = c.tenant_full_name
        lines.append(f"{i}. `{c.contract_number}` — {short_name} — {date_str}")

    return "\n".join(lines)


def _pagination_keyboard(offset: int, total: int) -> InlineKeyboardMarkup | None:
    """Build [Назад] [Вперёд] keyboard if needed."""
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"hist:{offset - PAGE_SIZE}"))
    if offset + PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"hist:{offset + PAGE_SIZE}"))

    if not buttons:
        return None
    return InlineKeyboardMarkup([buttons])


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history — show first page of contracts."""
    contracts, total = await database.get_contracts(offset=0, limit=PAGE_SIZE)
    text = _format_contract_list(contracts, 0, total)
    kb = _pagination_keyboard(0, total)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def history_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination button press."""
    query = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])
    offset = max(0, offset)

    contracts, total = await database.get_contracts(offset=offset, limit=PAGE_SIZE)
    text = _format_contract_list(contracts, offset, total)
    kb = _pagination_keyboard(offset, total)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


def get_history_handlers() -> list:
    """Return handlers to register in the application."""
    return [
        CommandHandler("history", cmd_history),
        CallbackQueryHandler(history_page, pattern=r"^hist:\d+$"),
    ]
