"""Contract creation ConversationHandler — all FSM states and callbacks.

Public API:
    build_conversation_handler() -> ConversationHandler
"""
import logging
import re
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import ocr_service
from document_service import generate_contract_number
from models import ContractData
from validators import validate_age, validate_amount, validate_date, validate_email, validate_phone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State integer constants
# ---------------------------------------------------------------------------
(
    GROUP,
    APARTMENT,
    CONTRACT_DATE,
    ACT_DATE,
    MONTHLY_AMOUNT,
    DEPOSIT_AMOUNT,
    DEPOSIT_METHOD,
    PHONE,
    EMAIL,
    PASSPORT_PAGE1,
    PASSPORT_PAGE2,
    CONFIRM,
) = range(12)

# ---------------------------------------------------------------------------
# Apartment data
# ---------------------------------------------------------------------------
APARTMENTS: dict[str, list[str]] = {
    "Г39": ["39/1", "39/2", "39/3", "39/4", "39/5", "39/6", "39/7"],
    "Г38": ["38/1", "38/2", "38/3", "38/4", "38/5", "38/6", "38/7", "38/8"],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send group selection keyboard and enter GROUP state."""
    context.user_data.clear()
    keyboard = [
        [
            InlineKeyboardButton("Г39", callback_data="Г39"),
            InlineKeyboardButton("Г38", callback_data="Г38"),
        ]
    ]
    await update.message.reply_text(
        "Создание договора аренды.\nВыберите группу объектов:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return GROUP


# ---------------------------------------------------------------------------
# Group / Apartment selection
# ---------------------------------------------------------------------------

async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle group selection — show apartment keyboard."""
    query = update.callback_query
    await query.answer()
    group = query.data
    context.user_data["group"] = group

    apartments = APARTMENTS[group]
    # Build rows of 4 buttons max
    rows = [
        [InlineKeyboardButton(apt, callback_data=apt) for apt in apartments[i:i + 4]]
        for i in range(0, len(apartments), 4)
    ]
    await query.edit_message_text(
        f"Группа {group}. Выберите квартиру:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return APARTMENT


async def handle_apartment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle apartment selection — ask for contract date."""
    query = update.callback_query
    await query.answer()
    context.user_data["apartment"] = query.data
    await query.edit_message_text("Введите дату договора (ДД.ММ.ГГГГ):")
    return CONTRACT_DATE


# ---------------------------------------------------------------------------
# Text-input states
# ---------------------------------------------------------------------------

async def handle_contract_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store contract date."""
    result = validate_date(update.message.text)
    if isinstance(result, str):
        await update.message.reply_text(result)
        return CONTRACT_DATE
    context.user_data["contract_date"] = result
    await update.message.reply_text("Введите дату Акта приёма-передачи (ДД.ММ.ГГГГ):")
    return ACT_DATE


async def handle_act_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store act date."""
    result = validate_date(update.message.text)
    if isinstance(result, str):
        await update.message.reply_text(result)
        return ACT_DATE
    context.user_data["act_date"] = result
    await update.message.reply_text("Введите сумму ежемесячной аренды (например, 50000):")
    return MONTHLY_AMOUNT


async def handle_monthly_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store monthly rent amount."""
    result = validate_amount(update.message.text)
    if isinstance(result, str):
        await update.message.reply_text(result)
        return MONTHLY_AMOUNT
    context.user_data["monthly_amount"] = result
    await update.message.reply_text("Введите сумму депозита:")
    return DEPOSIT_AMOUNT


async def handle_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store deposit amount — show payment method keyboard."""
    result = validate_amount(update.message.text)
    if isinstance(result, str):
        await update.message.reply_text(result)
        return DEPOSIT_AMOUNT
    context.user_data["deposit_amount"] = result
    half = int(result / 2)
    keyboard = [
        [
            InlineKeyboardButton("Единовременно", callback_data="lump"),
            InlineKeyboardButton(f"50%+50% ({half}р + {half}р)", callback_data="split"),
        ]
    ]
    await update.message.reply_text(
        "Выберите способ внесения депозита:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return DEPOSIT_METHOD


async def handle_deposit_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deposit method selection — ask for tenant phone."""
    query = update.callback_query
    await query.answer()
    context.user_data["deposit_split"] = (query.data == "split")
    await query.edit_message_text("Введите телефон арендатора (формат: +7 XXX XXX XX XX):")
    return PHONE


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store tenant phone number."""
    result = validate_phone(update.message.text)
    # validate_phone returns str on both success (+7XXXXXXXXXX) and error.
    # Detect success by matching the normalized E.164 format exactly.
    if not re.fullmatch(r'\+7\d{10}', result):
        await update.message.reply_text(result)
        return PHONE
    context.user_data["tenant_phone"] = result
    await update.message.reply_text("Введите email арендатора:")
    return EMAIL


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store tenant email — ask for passport page 1."""
    result = validate_email(update.message.text)
    # validate_email returns str on both success (lowercased email) and error.
    # Detect success by matching a basic email pattern.
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', result):
        await update.message.reply_text(result)
        return EMAIL
    context.user_data["tenant_email"] = result
    await update.message.reply_text(
        "Отправьте *первую страницу паспорта* арендатора как файл "
        "(Прикрепить → Файл, не как фото):",
        parse_mode="Markdown",
    )
    return PASSPORT_PAGE1


# ---------------------------------------------------------------------------
# Passport upload handlers
# ---------------------------------------------------------------------------

async def handle_passport_page1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Download and store passport page 1 as bytes."""
    tg_file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = bytes(await tg_file.download_as_bytearray())
    context.user_data["passport_page1"] = file_bytes
    await update.message.reply_text(
        "Страница 1 принята.\nТеперь отправьте *страницу с пропиской* как файл "
        "(Прикрепить → Файл):",
        parse_mode="Markdown",
    )
    return PASSPORT_PAGE2


async def handle_passport_photo_warning_p1(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Warn user to send passport as file, not photo (page 1)."""
    await update.message.reply_text(
        "Пожалуйста, отправьте фото паспорта как *файл* (Прикрепить → Файл), "
        "а не как фотографию — иначе качество будет недостаточным для распознавания.",
        parse_mode="Markdown",
    )
    return PASSPORT_PAGE1


async def handle_passport_page2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Download passport page 2, run OCR, show summary with confirm/retry keyboard."""
    tg_file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = bytes(await tg_file.download_as_bytearray())
    context.user_data["passport_page2"] = file_bytes

    await update.message.reply_text("Распознаю паспорт... ⏳")

    fields = await ocr_service.extract_passport_fields(
        context.user_data["passport_page1"], file_bytes
    )
    context.user_data["passport_fields"] = fields

    # Pop large bytes after OCR to keep PicklePersistence file small
    context.user_data.pop("passport_page1", None)
    context.user_data.pop("passport_page2", None)

    unclear = ocr_service.get_unclear_fields(fields)
    summary = ocr_service.format_ocr_summary(fields)
    if unclear:
        summary += f"\n\n⚠️ Нечитаемые поля: {', '.join(unclear)}"

    keyboard = [
        [
            InlineKeyboardButton("Подтвердить ✅", callback_data="confirm"),
            InlineKeyboardButton("Переснять паспорт 🔄", callback_data="retry_passport"),
        ]
    ]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRM


async def handle_passport_photo_warning_p2(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Warn user to send passport as file, not photo (page 2)."""
    await update.message.reply_text(
        "Пожалуйста, отправьте фото паспорта как *файл* (Прикрепить → Файл), "
        "а не как фотографию — иначе качество будет недостаточным для распознавания.",
        parse_mode="Markdown",
    )
    return PASSPORT_PAGE2


# ---------------------------------------------------------------------------
# Confirmation handler
# ---------------------------------------------------------------------------

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirm or retry_passport callback at the CONFIRM state."""
    query = update.callback_query
    await query.answer()

    if query.data == "retry_passport":
        context.user_data.pop("passport_page1", None)
        context.user_data.pop("passport_page2", None)
        context.user_data.pop("passport_fields", None)
        await query.edit_message_text(
            "Отправьте *первую страницу паспорта* как файл:",
            parse_mode="Markdown",
        )
        return PASSPORT_PAGE1

    # query.data == "confirm"
    ud = context.user_data
    fields = ud["passport_fields"]

    # Parse OCR dates
    tenant_dob = validate_date(fields["tenant_dob"])
    if isinstance(tenant_dob, str):
        await query.edit_message_text(
            f"Ошибка распознавания даты рождения: {tenant_dob}\nОтправьте паспорт заново."
        )
        return PASSPORT_PAGE1

    passport_issued_date = validate_date(fields["passport_issued_date"])
    if isinstance(passport_issued_date, str):
        await query.edit_message_text(
            f"Ошибка распознавания даты выдачи паспорта: {passport_issued_date}\n"
            "Отправьте паспорт заново."
        )
        return PASSPORT_PAGE1

    # Validate age
    age_ok = validate_age(tenant_dob, ud["contract_date"])
    if isinstance(age_ok, str):
        await query.edit_message_text(
            f"Ошибка: {age_ok}\nНачните заново: /start"
        )
        return ConversationHandler.END

    # Generate contract number
    contract_number = generate_contract_number(ud["group"], ud["apartment"], ud["contract_date"])

    # Assemble ContractData
    contract_data = ContractData(
        contract_number=contract_number,
        group=ud["group"],
        apartment=ud["apartment"],
        tenant_full_name=fields["tenant_full_name"],
        tenant_dob=tenant_dob,
        tenant_birthplace=fields["tenant_birthplace"],
        tenant_gender=fields["tenant_gender"],
        tenant_address=fields["tenant_address"],
        passport_series=fields["passport_series"],
        passport_number=fields["passport_number"],
        passport_issued_date=passport_issued_date,
        passport_issued_by=fields["passport_issued_by"],
        passport_division_code=fields["passport_division_code"],
        tenant_phone=ud["tenant_phone"],
        tenant_email=ud["tenant_email"],
        contract_date=ud["contract_date"],
        act_date=ud["act_date"],
        monthly_amount=ud["monthly_amount"],
        deposit_amount=ud["deposit_amount"],
        deposit_split=ud.get("deposit_split", False),
    )

    context.user_data["contract_data"] = contract_data
    logger.info("ContractData assembled: contract_number=%s", contract_number)

    await query.edit_message_text(
        f"✅ Данные подтверждены.\n"
        f"Номер договора: {contract_number}\n"
        "Генерация договора будет выполнена в следующем шаге."
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /cancel and fallback
# ---------------------------------------------------------------------------

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel contract creation at any state."""
    context.user_data.clear()
    await update.message.reply_text(
        "Создание договора отменено. Для начала введите /start"
    )
    return ConversationHandler.END


async def handle_unexpected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all fallback — re-prompt without advancing state."""
    await update.message.reply_text(
        "Не понимаю этого сообщения. Следуйте инструкциям бота.\n"
        "Для отмены введите /cancel"
    )
    return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_conversation_handler() -> ConversationHandler:
    """Assemble and return the ConversationHandler for contract creation."""
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            GROUP:          [CallbackQueryHandler(handle_group)],
            APARTMENT:      [CallbackQueryHandler(handle_apartment)],
            CONTRACT_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_date)],
            ACT_DATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_act_date)],
            MONTHLY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_monthly_amount)],
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_amount)],
            DEPOSIT_METHOD: [CallbackQueryHandler(handle_deposit_method)],
            PHONE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
            EMAIL:          [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            PASSPORT_PAGE1: [
                MessageHandler(filters.Document.ALL, handle_passport_page1),
                MessageHandler(filters.PHOTO, handle_passport_photo_warning_p1),
            ],
            PASSPORT_PAGE2: [
                MessageHandler(filters.Document.ALL, handle_passport_page2),
                MessageHandler(filters.PHOTO, handle_passport_photo_warning_p2),
            ],
            CONFIRM:        [CallbackQueryHandler(handle_confirm)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            MessageHandler(filters.ALL, handle_unexpected),
        ],
        name="contract_conversation",
        persistent=True,
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
