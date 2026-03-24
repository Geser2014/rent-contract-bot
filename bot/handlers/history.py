"""Handler for /history command — list contracts with pagination, open PDF on tap."""
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import database

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def _short_name(full_name: str) -> str:
    """Покровский Даниил Артурович -> Покровский Д.А."""
    parts = full_name.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return full_name


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history — show last 10 contracts."""
    contracts, total = await database.get_contracts(offset=0, limit=PAGE_SIZE)
    if not contracts:
        await update.message.reply_text("📋 Договоров пока нет.")
        return

    rows = []
    for c in contracts:
        date_str = c.contract_date.strftime("%d.%m.%Y")
        label = f"{c.contract_number} — {_short_name(c.tenant_full_name)} — {date_str}"
        rows.append([InlineKeyboardButton(label, callback_data=f"hopen:{c.id}")])

    text = f"📋 *Последние договоры* ({len(contracts)} из {total}):"
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows),
    )


async def history_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send PDF file when contract button is tapped."""
    query = update.callback_query
    await query.answer()
    contract_id = int(query.data.split(":")[1])

    contract = await database.get_contract_by_id(contract_id)
    if not contract:
        await query.answer("Договор не найден", show_alert=True)
        return

    if not contract.pdf_path or not Path(contract.pdf_path).exists():
        await query.answer("PDF файл не найден на диске", show_alert=True)
        return

    with open(contract.pdf_path, "rb") as f:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=f,
            filename=f"Договор_{contract.contract_number.replace('/', '_')}.pdf",
            caption=f"📄 Договор №{contract.contract_number}\n"
                    f"👤 {contract.tenant_full_name}\n"
                    f"📅 {contract.contract_date.strftime('%d.%m.%Y')}",
        )


def get_history_handlers() -> list:
    """Return handlers to register in the application."""
    return [
        CommandHandler("history", cmd_history),
        CallbackQueryHandler(history_open, pattern=r"^hopen:\d+$"),
    ]
