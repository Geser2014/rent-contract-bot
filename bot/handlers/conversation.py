"""Contract creation ConversationHandler — all FSM states and callbacks.

Public API:
    build_conversation_handler() -> ConversationHandler
"""
import datetime
import logging
import re
import subprocess
from decimal import Decimal
from pathlib import Path

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
    AUTH,
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
    RESIDENTS_CHOICE,
    ROOMMATE_PAGE1,
    ROOMMATE_PAGE2,
    ROOMMATE_CONFIRM_OCR,
    ROOMMATE_EDIT_FIELD,
    ROOMMATE_MORE,
    EXTRA_CONDITIONS_CHOICE,
    EXTRA_CONDITIONS_INPUT,
    PASSPORT_PAGE1,
    PASSPORT_PAGE2,
    CONFIRM_OCR,
    EDIT_FIELD,
    CHOOSE_FORMAT,
    CONFIRM,
) = range(26)

# Authorized users file
import json as _json
import hmac
import time as _time
_AUTH_FILE = config.STORAGE_DIR / "authorized_users.json"

# Brute-force protection: {user_id: {"attempts": int, "locked_until": float}}
_failed_attempts: dict[int, dict] = {}
_MAX_ATTEMPTS = 3
_LOCKOUT_SECONDS = 86400  # 24 hours

def _load_authorized_users() -> set[int]:
    if _AUTH_FILE.exists():
        return set(_json.loads(_AUTH_FILE.read_text()))
    return set()

def _save_authorized_user(user_id: int) -> None:
    users = _load_authorized_users()
    users.add(user_id)
    _AUTH_FILE.write_text(_json.dumps(list(users)))

def _is_locked_out(user_id: int) -> bool:
    info = _failed_attempts.get(user_id)
    if not info:
        return False
    if info["attempts"] >= _MAX_ATTEMPTS:
        if _time.time() < info["locked_until"]:
            return True
        # Lockout expired — reset
        del _failed_attempts[user_id]
        return False
    return False

def _record_failed_attempt(user_id: int) -> int:
    info = _failed_attempts.setdefault(user_id, {"attempts": 0, "locked_until": 0})
    info["attempts"] += 1
    if info["attempts"] >= _MAX_ATTEMPTS:
        info["locked_until"] = _time.time() + _LOCKOUT_SECONDS
    return _MAX_ATTEMPTS - info["attempts"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check auth, then show group selection."""
    import config
    user_id = update.effective_user.id

    # If no password configured — skip auth
    if not config.BOT_PASSWORD:
        return await _show_groups(update, context)

    # If already authorized — skip auth
    if user_id in _load_authorized_users():
        return await _show_groups(update, context)

    # Ask for password
    await update.message.reply_text("Введите пароль для доступа к боту:")
    return AUTH


async def handle_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Check password and authorize user."""
    import config
    user_id = update.effective_user.id
    password = update.message.text.strip()

    # Check lockout
    if _is_locked_out(user_id):
        await update.message.reply_text("⛔ Слишком много попыток. Доступ заблокирован на 24 часа.")
        return ConversationHandler.END

    if hmac.compare_digest(password, config.BOT_PASSWORD):
        _save_authorized_user(user_id)
        _failed_attempts.pop(user_id, None)  # Clear failed attempts
        logger.info("User %d authorized", user_id)
        await update.message.reply_text("✅ Доступ разрешён!")
        return await _show_groups(update, context)
    else:
        remaining = _record_failed_attempt(user_id)
        if remaining <= 0:
            await update.message.reply_text("⛔ Слишком много попыток. Доступ заблокирован на 24 часа.")
            return ConversationHandler.END
        await update.message.reply_text(f"❌ Неверный пароль. Осталось попыток: {remaining}")
        return AUTH


async def _show_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show group selection keyboard."""
    from document_service import APARTMENTS_DATA
    context.user_data.clear()
    groups = [g for g in APARTMENTS_DATA.keys()]
    rows = [
        [InlineKeyboardButton(g, callback_data=g) for g in groups[i:i+2]]
        for i in range(0, len(groups), 2)
    ]
    await update.message.reply_text(
        "Создание договора аренды.\nВыберите группу объектов:",
        reply_markup=InlineKeyboardMarkup(rows),
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
        from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
        await query.edit_message_text(f"✅ Дата Акта: {result.strftime('%d.%m.%Y')}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Выберите срок договора:",
            reply_markup=ReplyKeyboardMarkup(
                [["360 дней", "Ввести вручную"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return CONTRACT_DURATION
    return ACT_DATE


async def handle_contract_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and store contract duration in days."""
    from telegram import ReplyKeyboardRemove
    text = update.message.text.strip()
    if text == "360 дней":
        text = "360"
    elif text == "Ввести вручную":
        await update.message.reply_text(
            "Введите срок договора в днях:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CONTRACT_DURATION
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("Введите положительное целое число (например, 365):")
        return CONTRACT_DURATION
    context.user_data["contract_duration"] = text
    await update.message.reply_text(
        "Введите сумму ежемесячной аренды (например, 50000):",
        reply_markup=ReplyKeyboardRemove(),
    )
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
    if "@" not in result:
        # validate_email returns error string (no @ in it) on failure
        await update.message.reply_text(result)
        return EMAIL
    context.user_data["tenant_email"] = result
    await update.message.reply_text("Введите Telegram арендатора (например, @username):")
    return TELEGRAM


async def handle_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store Telegram username — ask about co-residents."""
    context.user_data["telegram"] = update.message.text.strip()
    context.user_data.setdefault("roommates", [])
    keyboard = [
        [
            InlineKeyboardButton("1 человек", callback_data="residents_alone"),
            InlineKeyboardButton("Совместное", callback_data="residents_with"),
        ]
    ]
    await update.message.reply_text(
        "Кто будет проживать в квартире?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return RESIDENTS_CHOICE


async def handle_residents_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle alone/with selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "residents_alone":
        context.user_data["residents"] = "Нет"
        await query.edit_message_text(
            "Дополнительные условия?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Нет", callback_data="extra_no"),
                InlineKeyboardButton("Ввести", callback_data="extra_yes"),
            ]
        ])
        )
        return EXTRA_CONDITIONS_CHOICE

    # residents_with — start roommate passport scan
    await query.edit_message_text(
        f"Сожитель {len(context.user_data['roommates']) + 1}.\n"
        "Отправьте *первую страницу паспорта* сожителя как файл:",
        parse_mode="Markdown",
    )
    return ROOMMATE_PAGE1


# ---------------------------------------------------------------------------
# Roommate passport OCR (reuses same OCR service)
# ---------------------------------------------------------------------------

async def handle_roommate_page1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Download roommate passport page 1."""
    tg_file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = bytes(await tg_file.download_as_bytearray())
    context.user_data["_roommate_page1"] = file_bytes
    await update.message.reply_text(
        "Страница 1 принята.\nТеперь отправьте *страницу с пропиской* сожителя как файл:",
        parse_mode="Markdown",
    )
    return ROOMMATE_PAGE2


async def handle_roommate_photo_warning(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Warn: send as file, not photo."""
    await update.message.reply_text(
        "Отправьте как *файл* (Прикрепить → Файл), не как фотографию.",
        parse_mode="Markdown",
    )
    # Return to whichever roommate page state we're in
    if "_roommate_page1" in context.user_data:
        return ROOMMATE_PAGE2
    return ROOMMATE_PAGE1


async def handle_roommate_page2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Download roommate page 2, run OCR, show results."""
    tg_file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = bytes(await tg_file.download_as_bytearray())

    await update.message.reply_text("Распознаю паспорт сожителя... ⏳")

    try:
        fields = await ocr_service.extract_passport_fields(
            context.user_data["_roommate_page1"], file_bytes
        )
    except (anthropic.APIError, ValueError) as exc:
        logger.error("Roommate OCR failed: %s", exc)
        context.user_data.pop("_roommate_page1", None)
        await update.message.reply_text(
            "Не удалось распознать. Попробуйте снова — отправьте первую страницу:"
        )
        return ROOMMATE_PAGE1

    context.user_data.pop("_roommate_page1", None)
    context.user_data["_roommate_fields"] = fields

    # Show results with field picker
    return await _show_roommate_confirm(update.message, context)


async def _show_roommate_confirm(message, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show roommate OCR results with Да/Нет."""
    fields = context.user_data["_roommate_fields"]
    summary = ocr_service.format_ocr_summary(fields)

    keyboard = [
        [
            InlineKeyboardButton("Да ✅", callback_data="rm_ocr_ok"),
            InlineKeyboardButton("Нет, исправить ✏️", callback_data="rm_ocr_edit"),
        ],
        [InlineKeyboardButton("Переснять 🔄", callback_data="rm_ocr_retry")],
    ]
    await message.reply_text(
        f"📋 *Данные сожителя:*\n\n{summary}\n\nВсё верно?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ROOMMATE_CONFIRM_OCR


async def handle_roommate_confirm_ocr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle roommate OCR confirm/edit/retry."""
    query = update.callback_query
    await query.answer()

    if query.data == "rm_ocr_retry":
        context.user_data.pop("_roommate_fields", None)
        await query.edit_message_text(
            "Отправьте *первую страницу паспорта* сожителя как файл:",
            parse_mode="Markdown",
        )
        return ROOMMATE_PAGE1

    if query.data == "rm_ocr_ok":
        return await _save_roommate_and_ask_more(query, context)

    if query.data == "rm_ocr_edit":
        return await _show_roommate_field_picker(query, context)

    # Handle field selection
    if query.data.startswith("rm_edit_field:"):
        field_key = query.data.split(":", 1)[1]
        context.user_data["_rm_editing_field"] = field_key
        label = dict(_EDITABLE_FIELDS).get(field_key, field_key)
        current = context.user_data["_roommate_fields"].get(field_key, "—")
        await query.edit_message_text(
            f"✏️ *{label}*\nТекущее: `{current}`\n\nВведите новое значение:",
            parse_mode="Markdown",
        )
        return ROOMMATE_EDIT_FIELD

    return ROOMMATE_CONFIRM_OCR


async def _show_roommate_field_picker(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show field buttons for roommate editing."""
    fields = context.user_data["_roommate_fields"]
    rows = []
    for field_key, label in _EDITABLE_FIELDS:
        value = fields.get(field_key, "—")
        short_val = value[:25] + "…" if len(value) > 25 else value
        rows.append([InlineKeyboardButton(
            f"{label}: {short_val}",
            callback_data=f"rm_edit_field:{field_key}",
        )])
    rows.append([
        InlineKeyboardButton("✅ Готово", callback_data="rm_ocr_ok"),
        InlineKeyboardButton("🔄 Переснять", callback_data="rm_ocr_retry"),
    ])
    await query.edit_message_text(
        "Нажмите на поле для исправления:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return ROOMMATE_CONFIRM_OCR


async def handle_roommate_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent new value for roommate field."""
    field_key = context.user_data.pop("_rm_editing_field", None)
    if field_key:
        context.user_data["_roommate_fields"][field_key] = update.message.text.strip()
        label = dict(_EDITABLE_FIELDS).get(field_key, field_key)
        await update.message.reply_text(f"✅ {label} обновлено.")

    # Show field picker again
    fields = context.user_data["_roommate_fields"]
    rows = []
    for fk, lbl in _EDITABLE_FIELDS:
        value = fields.get(fk, "—")
        short_val = value[:25] + "…" if len(value) > 25 else value
        rows.append([InlineKeyboardButton(
            f"{lbl}: {short_val}",
            callback_data=f"rm_edit_field:{fk}",
        )])
    rows.append([
        InlineKeyboardButton("✅ Готово", callback_data="rm_ocr_ok"),
        InlineKeyboardButton("🔄 Переснять", callback_data="rm_ocr_retry"),
    ])
    await update.message.reply_text(
        "Нажмите на поле для исправления или «Готово»:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return ROOMMATE_CONFIRM_OCR


def _format_roommate_string(fields: dict) -> str:
    """Format roommate data as a single text line for the contract."""
    return (
        f"{fields.get('tenant_full_name', '___')}, "
        f"{fields.get('tenant_gender', '___')}, "
        f"{fields.get('tenant_dob', '___')} г.р., "
        f"место рождения: {fields.get('tenant_birthplace', '___')}, "
        f"паспорт {fields.get('passport_series', '___')} {fields.get('passport_number', '___')}, "
        f"выдан {fields.get('passport_issued_by', '___')}, "
        f"{fields.get('passport_issued_date', '___')} г., "
        f"код подразделения {fields.get('passport_division_code', '___')}, "
        f"зарег. по адресу: {fields.get('tenant_address', '___')}"
    )


async def _save_roommate_and_ask_more(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save roommate data and ask if there's another one (max 2)."""
    fields = context.user_data.pop("_roommate_fields")
    roommate_str = _format_roommate_string(fields)
    context.user_data["roommates"].append(roommate_str)

    count = len(context.user_data["roommates"])

    if count >= 5:
        # Max reached
        context.user_data["residents"] = "; ".join(context.user_data["roommates"])
        await query.edit_message_text(
            f"✅ Записано {count} сожителя.\n\n"
            "Дополнительные условия?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Нет", callback_data="extra_no"),
                InlineKeyboardButton("Ввести", callback_data="extra_yes"),
            ]
        ])
        )
        return EXTRA_CONDITIONS_CHOICE

    # Ask for more
    keyboard = [
        [
            InlineKeyboardButton("Ещё один жилец", callback_data="roommate_more_yes"),
            InlineKeyboardButton("Больше нет", callback_data="roommate_more_no"),
        ]
    ]
    await query.edit_message_text(
        f"✅ Сожитель {count} записан: {fields.get('tenant_full_name', '___')}\n\n"
        "Ещё кто-то будет проживать?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ROOMMATE_MORE


async def handle_roommate_more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 'one more roommate' or 'no more'."""
    query = update.callback_query
    await query.answer()

    if query.data == "roommate_more_yes":
        await query.edit_message_text(
            f"Сожитель {len(context.user_data['roommates']) + 1}.\n"
            "Отправьте *первую страницу паспорта* сожителя как файл:",
            parse_mode="Markdown",
        )
        return ROOMMATE_PAGE1

    # No more
    context.user_data["residents"] = "; ".join(context.user_data["roommates"])
    await query.edit_message_text(
        "Дополнительные условия?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Нет", callback_data="extra_no"),
                InlineKeyboardButton("Ввести", callback_data="extra_yes"),
            ]
        ])
    )
    return EXTRA_CONDITIONS_CHOICE


async def handle_extra_conditions_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle Нет/Ввести for extra conditions."""
    query = update.callback_query
    await query.answer()

    if query.data == "extra_no":
        context.user_data["extra_conditions"] = "Нет"
        await query.edit_message_text(
            "Отправьте *первую страницу паспорта* арендатора как файл "
            "(Прикрепить → Файл, не как фото):",
            parse_mode="Markdown",
        )
        return PASSPORT_PAGE1

    # extra_yes
    await query.edit_message_text("Введите дополнительные условия:")
    return EXTRA_CONDITIONS_INPUT


async def handle_extra_conditions_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store typed extra conditions — ask for passport."""
    context.user_data["extra_conditions"] = update.message.text.strip()
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
# OCR confirmation + field editing by selection
# ---------------------------------------------------------------------------

_EDITABLE_FIELDS = [
    ("tenant_full_name",       "ФИО"),
    ("tenant_dob",             "Дата рождения"),
    ("tenant_birthplace",      "Место рождения"),
    ("tenant_gender",          "Пол"),
    ("passport_series",        "Серия"),
    ("passport_number",        "Номер"),
    ("passport_issued_date",   "Дата выдачи"),
    ("passport_issued_by",     "Кем выдан"),
    ("passport_division_code", "Код подр."),
    ("tenant_address",         "Адрес рег."),
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
        return await _show_final_confirm(update, context)

    if query.data == "ocr_edit":
        return await _show_field_picker(query, context)

    # Handle field selection: "edit_field:tenant_full_name"
    if query.data.startswith("edit_field:"):
        field_key = query.data.split(":", 1)[1]
        context.user_data["_editing_field"] = field_key
        label = dict(_EDITABLE_FIELDS).get(field_key, field_key)
        current = context.user_data["passport_fields"].get(field_key, "—")
        await query.edit_message_text(
            f"✏️ *{label}*\n\nТекущее значение: `{current}`\n\nВведите новое значение:",
            parse_mode="Markdown",
        )
        return EDIT_FIELD

    return CONFIRM_OCR


async def _show_field_picker(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show buttons for each field — tap to edit that field."""
    fields = context.user_data["passport_fields"]

    rows = []
    for field_key, label in _EDITABLE_FIELDS:
        value = fields.get(field_key, "—")
        # Truncate long values for button text
        short_val = value[:25] + "…" if len(value) > 25 else value
        rows.append([InlineKeyboardButton(
            f"{label}: {short_val}",
            callback_data=f"edit_field:{field_key}",
        )])

    rows.append([
        InlineKeyboardButton("✅ Готово", callback_data="ocr_ok"),
        InlineKeyboardButton("🔄 Переснять", callback_data="ocr_retry"),
    ])

    await query.edit_message_text(
        "Нажмите на поле, которое нужно исправить:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return CONFIRM_OCR


async def handle_edit_field_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent new value for selected field — show field picker again."""
    field_key = context.user_data.pop("_editing_field", None)
    if field_key:
        context.user_data["passport_fields"][field_key] = update.message.text.strip()
        label = dict(_EDITABLE_FIELDS).get(field_key, field_key)
        await update.message.reply_text(f"✅ {label} обновлено.")

    # Show field picker again
    fields = context.user_data["passport_fields"]
    rows = []
    for fk, lbl in _EDITABLE_FIELDS:
        value = fields.get(fk, "—")
        short_val = value[:25] + "…" if len(value) > 25 else value
        rows.append([InlineKeyboardButton(
            f"{lbl}: {short_val}",
            callback_data=f"edit_field:{fk}",
        )])
    rows.append([
        InlineKeyboardButton("✅ Готово", callback_data="ocr_ok"),
        InlineKeyboardButton("🔄 Переснять", callback_data="ocr_retry"),
    ])
    await update.message.reply_text(
        "Нажмите на поле для исправления или «Готово»:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return CONFIRM_OCR


async def _show_final_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and proceed directly to DOCX generation."""
    query = update.callback_query
    context.user_data["output_format"] = "docx"
    await query.edit_message_text("✅ Данные подтверждены.\nГенерирую договор...")
    return await handle_confirm(update, context)


async def handle_choose_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle format selection — store choice and trigger generation."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_confirm":
        context.user_data.clear()
        await query.edit_message_text("Создание договора отменено. Для начала введите /start")
        return ConversationHandler.END

    # Store format choice and go to generation
    context.user_data["output_format"] = query.data.replace("fmt_", "")  # "pdf", "docx", "both"
    # Trigger handle_confirm directly by returning CONFIRM with a synthetic callback
    return await handle_confirm(update, context)


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
    """Generate contract — called from handle_choose_format."""
    query = update.callback_query
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

    output_format = ud.get("output_format", "pdf")
    safe_name = contract_number.replace("/", "_")
    chat_id = query.message.chat_id

    # Generate contract (always produces filled file + PDF)
    try:
        pdf_path = await generate_contract(contract_data, extra)
    except subprocess.TimeoutExpired as exc:
        logger.error("PDF generation timed out: %s", exc)
        context.user_data.clear()
        await context.bot.send_message(
            chat_id=chat_id,
            text="Генерация договора заняла слишком долго. Попробуйте ещё раз позже.",
        )
        return ConversationHandler.END
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("PDF generation failed: %s", exc)
        context.user_data.clear()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Не удалось создать договор: {exc}",
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
            chat_id=chat_id,
            text="Договор с таким номером уже существует. Начните заново: /start",
        )
        return ConversationHandler.END
    logger.info("Contract saved to DB: id=%d contract_number=%s", row_id, contract_number)

    # Send files based on chosen format
    if output_format in ("pdf", "both"):
        with open(pdf_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=f"Договор_{safe_name}.pdf",
                caption=f"📄 Договор №{contract_number}",
            )

    if output_format in ("docx", "both"):
        # Find the filled DOCX/TXT source file next to the PDF
        pdf_p = Path(pdf_path)
        docx_file = pdf_p.with_suffix(".docx")
        txt_file = pdf_p.with_suffix(".txt")
        src_file = docx_file if docx_file.exists() else txt_file if txt_file.exists() else None
        if src_file and src_file.exists():
            suffix = src_file.suffix.upper().lstrip(".")
            with open(src_file, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=f"Договор_{safe_name}{src_file.suffix}",
                    caption=f"📝 Договор №{contract_number} ({suffix})",
                )

    await context.bot.send_message(chat_id=chat_id, text=f"✅ Договор №{contract_number} готов!")

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
            AUTH:             [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auth)],
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
            RESIDENTS_CHOICE: [CallbackQueryHandler(handle_residents_choice)],
            ROOMMATE_PAGE1: [
                MessageHandler(filters.Document.ALL, handle_roommate_page1),
                MessageHandler(filters.PHOTO, handle_roommate_photo_warning),
            ],
            ROOMMATE_PAGE2: [
                MessageHandler(filters.Document.ALL, handle_roommate_page2),
                MessageHandler(filters.PHOTO, handle_roommate_photo_warning),
            ],
            ROOMMATE_CONFIRM_OCR: [CallbackQueryHandler(handle_roommate_confirm_ocr)],
            ROOMMATE_EDIT_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_roommate_edit_field),
            ],
            ROOMMATE_MORE:    [CallbackQueryHandler(handle_roommate_more)],
            EXTRA_CONDITIONS_CHOICE: [CallbackQueryHandler(handle_extra_conditions_choice)],
            EXTRA_CONDITIONS_INPUT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_extra_conditions_input)],
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_field_text),
            ],
            CHOOSE_FORMAT:    [CallbackQueryHandler(handle_choose_format)],
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
