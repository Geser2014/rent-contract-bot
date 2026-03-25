"""Handler for /history — year → month → contract list → open PDF."""
import json as _json
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

import config
import database

logger = logging.getLogger(__name__)

_AUTH_FILE = config.STORAGE_DIR / "authorized_users.json"


def _is_authorized(user_id: int) -> bool:
    """Check if user is authorized."""
    if not config.BOT_PASSWORD:
        return True
    if _AUTH_FILE.exists():
        return user_id in set(_json.loads(_AUTH_FILE.read_text()))
    return False

_MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def _short_name(full_name: str) -> str:
    parts = full_name.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return full_name


# --- Step 1: Choose year ---

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available years as buttons."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа. Используйте /start для авторизации.")
        return
    years = await database.get_available_years()
    if not years:
        await update.message.reply_text("📋 Договоров пока нет.")
        return

    rows = [
        [InlineKeyboardButton(str(y), callback_data=f"hyear:{y}") for y in years[i:i+4]]
        for i in range(0, len(years), 4)
    ]
    await update.message.reply_text(
        "📋 Выберите год:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# --- Step 2: Choose month ---

async def handle_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show months that have contracts for selected year."""
    query = update.callback_query
    await query.answer()
    year = int(query.data.split(":")[1])

    months = await database.get_available_months(year)
    if not months:
        await query.edit_message_text(f"За {year} год договоров нет.")
        return

    rows = [
        [InlineKeyboardButton(_MONTH_NAMES[m], callback_data=f"hmonth:{year}:{m}") for m in months[i:i+3]]
        for i in range(0, len(months), 3)
    ]
    rows.append([InlineKeyboardButton("⬅️ Назад к годам", callback_data="hback_years")])

    await query.edit_message_text(
        f"📋 *{year}* — выберите месяц:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# --- Step 3: Show contracts ---

async def handle_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show contracts for selected year+month."""
    query = update.callback_query
    await query.answer()
    _, year_s, month_s = query.data.split(":")
    year, month = int(year_s), int(month_s)

    contracts = await database.get_contracts_by_month(year, month)
    if not contracts:
        await query.edit_message_text(f"За {_MONTH_NAMES[month]} {year} договоров нет.")
        return

    rows = []
    for c in contracts:
        date_str = c.contract_date.strftime("%d.%m.%Y")
        label = f"{c.contract_number} — {_short_name(c.tenant_full_name)} — {date_str}"
        rows.append([InlineKeyboardButton(label, callback_data=f"hopen:{c.id}")])

    rows.append([InlineKeyboardButton(f"⬅️ Назад к {year}", callback_data=f"hyear:{year}")])

    await query.edit_message_text(
        f"📋 *{_MONTH_NAMES[month]} {year}* ({len(contracts)} дог.):\nНажмите чтобы открыть PDF:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# --- Back to years ---

async def handle_back_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Go back to year selection."""
    query = update.callback_query
    await query.answer()

    years = await database.get_available_years()
    if not years:
        await query.edit_message_text("📋 Договоров пока нет.")
        return

    rows = [
        [InlineKeyboardButton(str(y), callback_data=f"hyear:{y}") for y in years[i:i+4]]
        for i in range(0, len(years), 4)
    ]
    await query.edit_message_text(
        "📋 Выберите год:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# --- Open PDF ---

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
    return [
        CommandHandler("history", cmd_history),
        CallbackQueryHandler(handle_year, pattern=r"^hyear:\d+$"),
        CallbackQueryHandler(handle_month, pattern=r"^hmonth:\d+:\d+$"),
        CallbackQueryHandler(handle_back_years, pattern=r"^hback_years$"),
        CallbackQueryHandler(history_open, pattern=r"^hopen:\d+$"),
    ]
