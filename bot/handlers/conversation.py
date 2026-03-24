"""Contract creation ConversationHandler — all FSM states and callbacks.

Public API:
    build_conversation_handler() -> ConversationHandler
"""
import datetime
import logging
import re
import subprocess
from decimal import Decimal

import anthropic
from sqlalchemy.exc import IntegrityError
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP

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
import database
from document_service import generate_contract, generate_contract_number, get_apartment_names
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
    CONTRACT_DURATION,
    MONTHLY_AMOUNT,
    DEPOSIT_AMOUNT,
    DEPOSIT_METHOD,
    PHONE,
    EMAIL,
    TELEGRAM,
    RESIDENTS,
    EXTRA_CONDITIONS,
    PASSPORT_PAGE1,
    PASSPORT_PAGE2,
    CONFIRM_OCR,
    EDIT_FIELD,
    CONFIRM,
) = range(18)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send group selection keyboard and enter GROUP state."""
    context.user_data.clear()
    keyboard = [
        [
            InlineKeyboardButton("Подольская 39", callback_data="Подольская 39"),
            InlineKeyboardButton("Подольская 38", callback_data="Подольская 38"),
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

    apartments = get_apartment_names(group)
    if not apartments:
        await query.edit_message_text(f"Нет квартир в группе {group}. Начните заново: /start")
        return ConversationHandler.END

    # Build rows of 3 buttons max
    rows = [
        [InlineKeyboardButton(apt, callback_data=apt) for apt in apartments[i:i + 3]]
        for i in range(0, len(apartments), 3)
    ]
    await query.edit_message_text(
        f"Группа {group}. Выберите квартиру:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return APARTMENT


async def handle_apartment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle apartment selection — show calendar for contract date."""
    query = update.callback_query
    await query.answer()
    context.user_data["apartment"] = query.data
    calendar, step = DetailedTelegramCalendar(locale="ru", min_date=datetime.date(2020, 1, 1)).build()
    await query.edit_message_text(
        f"Выберите дату договора ({LSTEP.get(step, step)}):",
        reply_markup=calendar,
    )
    return CONTRACT_DATE


# ---------------------------------------------------------------------------
# Text-input states
# ---------------------------------------------------------------------------

async def handle_contract_date_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show calendar for contract date selection."""
    query = update.callback_query
    await query.answer()
    calendar, step = DetailedTelegramCalendar(locale="ru", min_date=datetime.date(2020, 1, 1)).build()
    await query.edit_message_text(
        f"Выберите дату договора ({LSTEP.get(step, step)}):",
        reply_markup=calendar,
    )
    return CONTRACT_DATE


async def handle_contract_date_cal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle calendar callback for contract date."""
    query = update.callback_query
    await query.answer()
    result, key, step = DetailedTelegramCalendar(locale="ru", min_date=datetime.date(2020, 1, 1)).process(query.data)
    if not result and key:
        await query.edit_message_text(
            f"Выберите дату договора ({LSTEP.get(step, step)}):",
            reply_markup=key,
        )
        return CONTRACT_DATE
    if result:
        context.user_data["contract_date"] = result
        # Show calendar for act date
        calendar, step = DetailedTelegramCalendar(locale="ru", min_date=datetime.date(2020, 1, 1)).build()
        await query.edit_message_text(
            f"✅ Дата договора: {result.strftime('%d.%m.%Y')}\n\n"
            f"Выберите дату Акта приёма-передачи ({LSTEP.get(step, step)}):",
            reply_markup=calendar,
        )
        return ACT_DATE
    return CONTRACT_DATE


async def handle_act_date_cal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle calendar callback for act date."""
    query = update.callback_query
    await query.answer()
    result, key, step = DetailedTelegramCalendar(locale="ru", min_date=datetime.date(2020, 1, 1)).process(query.data)
    if not result and key:
        await query.edit_message_text(
            f"Выберите дату Акта приёма-передачи ({LSTEP.get(step, step)}):",
            reply_markup=key,
        )
        return ACT_DATE
    if result:
        context.user_data["act_date"] = result
        await query.edit_message_text(
            f"✅ Дата Акта: {result.strftime('%d.%m.%Y')}\n\n"
            "Введите срок договора в днях (например, 365):"
        )
        return CONTRACT_DURATION
    return ACT_DATE


async def handle_contract_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store contract duration in days."""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("Введите положительное целое число (например, 365):")
        return CONTRACT_DURATION
    context.user_data["contract_duration"] = text
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
    """Store tenant phone number (any format)."""
    context.user_data["tenant_phone"] = update.message.text.strip()
    await update.message.reply_text("Введите email арендатора:")
    return EMAIL


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store tenant email — ask for Telegram username."""
    result = validate_email(update.message.text)
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', result):
        await update.message.reply_text(result)
        return EMAIL
    context.user_data["tenant_email"] = result
    await update.message.reply_text("Введите Telegram арендатора (например, @username):")
    return TELEGRAM


async def handle_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store Telegram username — ask for residents list."""
    context.user_data["telegram"] = update.message.text.strip()
    await update.message.reply_text(
        'Кто будет проживать с арендатором?\n'
        '(Введите ФИО через запятую, или "нет" если только арендатор)'
    )
    return RESIDENTS


async def handle_residents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store residents — ask for extra conditions."""
    text = update.message.text.strip()
    if text.lower() in ("нет", "нету", "-", "только я"):
        context.user_data["residents"] = "Нет"
    else:
        context.user_data["residents"] = text
    await update.message.reply_text(
        'Дополнительные условия?\n'
        '(Введите текст или "нет")'
    )
    return EXTRA_CONDITIONS


async def handle_extra_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store extra conditions — ask for passport page 1."""
    text = update.message.text.strip()
    if text.lower() in ("нет", "нету", "-"):
        context.user_data["extra_conditions"] = "Нет"
    else:
        context.user_data["extra_conditions"] = text
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
    """Download passport page 2, run OCR, show summary with Да/Нет."""
    tg_file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = bytes(await tg_file.download_as_bytearray())
    context.user_data["passport_page2"] = file_bytes

    await update.message.reply_text("Распознаю паспорт... ⏳")

    try:
        fields = await ocr_service.extract_passport_fields(
            context.user_data["passport_page1"], file_bytes
        )
    except (anthropic.APIError, ValueError) as exc:
        logger.error("OCR failed: %s", exc)
        context.user_data.pop("passport_page1", None)
        context.user_data.pop("passport_page2", None)
        await update.message.reply_text(
            "Не удалось распознать паспорт. "
            "Попробуйте сфотографировать паспорт чётче и отправить заново."
        )
        return PASSPORT_PAGE1
    context.user_data["passport_fields"] = fields

    # Pop large bytes after OCR
    context.user_data.pop("passport_page1", None)
    context.user_data.pop("passport_page2", None)

    return await _show_ocr_confirm(update.message, context)


async def _show_ocr_confirm(message_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show OCR summary with Да/Нет/Переснять buttons."""
    fields = context.user_data["passport_fields"]
    summary = ocr_service.format_ocr_summary(fields)
    unclear = ocr_service.get_unclear_fields(fields)
    if unclear:
        labels = {f: ocr_service._FIELD_LABELS.get(f, f) for f in unclear}
        summary += "\n\n⚠️ Нечитаемые поля: " + ", ".join(labels.values())

    keyboard = [
        [
            InlineKeyboardButton("Да ✅", callback_data="ocr_ok"),
            InlineKeyboardButton("Нет, исправить ✏️", callback_data="ocr_edit"),
        ],
        [InlineKeyboardButton("Переснять паспорт 🔄", callback_data="ocr_retry")],
    ]

    send = getattr(message_or_query, "reply_text", None) or message_or_query.edit_message_text
    await send(
        f"📋 *Распознанные данные:*\n\n{summary}\n\nВсё верно?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRM_OCR


# ---------------------------------------------------------------------------
# OCR confirmation + field-by-field editing
# ---------------------------------------------------------------------------

# Ordered list of editable fields with Russian labels
_EDITABLE_FIELDS = [
    ("tenant_full_name",       "ФИО"),
    ("tenant_dob",             "Дата рождения"),
    ("tenant_birthplace",      "Место рождения"),
    ("tenant_gender",          "Пол"),
    ("passport_series",        "Серия паспорта"),
    ("passport_number",        "Номер паспорта"),
    ("passport_issued_date",   "Дата выдачи"),
    ("passport_issued_by",     "Кем выдан"),
    ("passport_division_code", "Код подразделения"),
    ("tenant_address",         "Адрес регистрации"),
]


async def handle_confirm_ocr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Да/Нет/Переснять after OCR."""
    query = update.callback_query
    await query.answer()

    if query.data == "ocr_retry":
        context.user_data.pop("passport_fields", None)
        await query.edit_message_text(
            "Отправьте *первую страницу паспорта* как файл:",
            parse_mode="Markdown",
        )
        return PASSPORT_PAGE1

    if query.data == "ocr_ok":
        # OCR confirmed — proceed to final contract confirm
        return await _show_final_confirm(query, context)

    if query.data == "ocr_edit":
        # Start editing fields one by one
        context.user_data["_edit_index"] = 0
        return await _ask_edit_field(query, context)

    return CONFIRM_OCR


async def _ask_edit_field(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show current field value and ask to edit or keep."""
    idx = context.user_data.get("_edit_index", 0)
    fields = context.user_data["passport_fields"]

    if idx >= len(_EDITABLE_FIELDS):
        # All fields reviewed — show summary again
        context.user_data.pop("_edit_index", None)
        return await _show_ocr_confirm_from_query(query, context)

    field_key, field_label = _EDITABLE_FIELDS[idx]
    current_value = fields.get(field_key, "—")

    keyboard = [[InlineKeyboardButton("Оставить ➡️", callback_data="edit_keep")]]
    await query.edit_message_text(
        f"*{field_label}:* `{current_value}`\n\n"
        "Отправьте новое значение или нажмите «Оставить»:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return EDIT_FIELD


async def _show_ocr_confirm_from_query(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Re-show OCR confirm after editing (from callback query context)."""
    fields = context.user_data["passport_fields"]
    summary = ocr_service.format_ocr_summary(fields)

    keyboard = [
        [
            InlineKeyboardButton("Да ✅", callback_data="ocr_ok"),
            InlineKeyboardButton("Нет, исправить ✏️", callback_data="ocr_edit"),
        ],
        [InlineKeyboardButton("Переснять паспорт 🔄", callback_data="ocr_retry")],
    ]
    await query.edit_message_text(
        f"📋 *Обновлённые данные:*\n\n{summary}\n\nВсё верно?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRM_OCR


async def handle_edit_field_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent new value for current field."""
    idx = context.user_data.get("_edit_index", 0)
    if idx < len(_EDITABLE_FIELDS):
        field_key, field_label = _EDITABLE_FIELDS[idx]
        context.user_data["passport_fields"][field_key] = update.message.text.strip()

    # Move to next field
    context.user_data["_edit_index"] = idx + 1
    return await _ask_edit_field_from_message(update, context)


async def handle_edit_field_keep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User pressed 'Keep' — skip to next field."""
    query = update.callback_query
    await query.answer()
    idx = context.user_data.get("_edit_index", 0)
    context.user_data["_edit_index"] = idx + 1
    return await _ask_edit_field(query, context)


async def _ask_edit_field_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show next edit field prompt (from text message context)."""
    idx = context.user_data.get("_edit_index", 0)
    fields = context.user_data["passport_fields"]

    if idx >= len(_EDITABLE_FIELDS):
        # All fields reviewed — show updated summary
        context.user_data.pop("_edit_index", None)
        summary = ocr_service.format_ocr_summary(fields)
        keyboard = [
            [
                InlineKeyboardButton("Да ✅", callback_data="ocr_ok"),
                InlineKeyboardButton("Нет, исправить ✏️", callback_data="ocr_edit"),
            ],
            [InlineKeyboardButton("Переснять паспорт 🔄", callback_data="ocr_retry")],
        ]
        await update.message.reply_text(
            f"📋 *Обновлённые данные:*\n\n{summary}\n\nВсё верно?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return CONFIRM_OCR

    field_key, field_label = _EDITABLE_FIELDS[idx]
    current_value = fields.get(field_key, "—")

    keyboard = [[InlineKeyboardButton("Оставить ➡️", callback_data="edit_keep")]]
    await update.message.reply_text(
        f"*{field_label}:* `{current_value}`\n\n"
        "Отправьте новое значение или нажмите «Оставить»:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return EDIT_FIELD


async def _show_final_confirm(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show final confirmation with all data before contract generation."""
    ud = context.user_data
    fields = ud["passport_fields"]

    keyboard = [
        [
            InlineKeyboardButton("Подтвердить ✅", callback_data="confirm"),
            InlineKeyboardButton("Отмена ❌", callback_data="cancel_confirm"),
        ]
    ]
    await query.edit_message_text(
        "✅ Паспортные данные подтверждены.\n\n"
        "Создать договор?",
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

    if query.data == "cancel_confirm":
        context.user_data.clear()
        await query.edit_message_text("Создание договора отменено. Для начала введите /start")
        return ConversationHandler.END

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

    # Extra fields not in ContractData
    extra = {
        "telegram": ud.get("telegram", "___"),
        "residents": ud.get("residents", "___"),
        "contract_duration": ud.get("contract_duration", "___"),
        "extra_conditions": ud.get("extra_conditions", "Нет"),
    }

    logger.info("ContractData assembled: contract_number=%s", contract_number)

    await query.edit_message_text(
        f"✅ Данные подтверждены. Номер договора: {contract_number}\n"
        "Генерирую договор... ⏳"
    )

    # Generate PDF
    try:
        pdf_path = await generate_contract(contract_data, extra)
    except subprocess.TimeoutExpired as exc:
        logger.error("PDF generation timed out: %s", exc)
        context.user_data.clear()
        await query.edit_message_text(
            "Генерация договора заняла слишком долго. Попробуйте ещё раз позже."
        )
        return ConversationHandler.END
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("PDF generation failed: %s", exc)
        context.user_data.clear()
        await query.edit_message_text(
            f"Не удалось создать договор: {exc}"
        )
        return ConversationHandler.END

    contract_data.pdf_path = pdf_path
    logger.info("PDF generated: %s", pdf_path)

    # Save to database
    try:
        row_id = await database.save_contract(contract_data)
    except IntegrityError as exc:
        logger.error("DB save failed (duplicate contract number?): %s", exc)
        context.user_data.clear()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Договор с таким номером уже существует. Начните заново: /start",
        )
        return ConversationHandler.END
    logger.info("Contract saved to DB: id=%d contract_number=%s", row_id, contract_number)

    # Send PDF to user
    chat_id = query.message.chat_id
    with open(pdf_path, "rb") as pdf_file:
        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_file,
            filename=f"Договор_{contract_number.replace('/', '_')}.pdf",
            caption=f"Договор аренды №{contract_number} готов.",
        )

    context.user_data.clear()
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
            GROUP:            [CallbackQueryHandler(handle_group)],
            APARTMENT:        [CallbackQueryHandler(handle_apartment)],
            CONTRACT_DATE:    [CallbackQueryHandler(handle_contract_date_cal)],
            ACT_DATE:         [CallbackQueryHandler(handle_act_date_cal)],
            CONTRACT_DURATION:[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_duration)],
            MONTHLY_AMOUNT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_monthly_amount)],
            DEPOSIT_AMOUNT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_amount)],
            DEPOSIT_METHOD:   [CallbackQueryHandler(handle_deposit_method)],
            PHONE:            [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
            EMAIL:            [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            TELEGRAM:         [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram)],
            RESIDENTS:        [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_residents)],
            EXTRA_CONDITIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_extra_conditions)],
            PASSPORT_PAGE1: [
                MessageHandler(filters.Document.ALL, handle_passport_page1),
                MessageHandler(filters.PHOTO, handle_passport_photo_warning_p1),
            ],
            PASSPORT_PAGE2: [
                MessageHandler(filters.Document.ALL, handle_passport_page2),
                MessageHandler(filters.PHOTO, handle_passport_photo_warning_p2),
            ],
            CONFIRM_OCR:      [CallbackQueryHandler(handle_confirm_ocr)],
            EDIT_FIELD: [
                CallbackQueryHandler(handle_edit_field_keep, pattern="^edit_keep$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_field_text),
            ],
            CONFIRM:          [CallbackQueryHandler(handle_confirm)],
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
