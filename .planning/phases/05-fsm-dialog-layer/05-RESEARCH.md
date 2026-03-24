# Phase 5: FSM Dialog Layer — Research

**Researched:** 2026-03-24
**Domain:** python-telegram-bot 22.x ConversationHandler, PicklePersistence, inline keyboards, async handlers
**Confidence:** HIGH — based on existing project codebase (phases 1-4 complete), prior stack/pitfalls/architecture research, and official PTB docs patterns

---

## Summary

Phase 5 is the integration phase that wires together all four completed services (validators, database, document_service, ocr_service) behind a ConversationHandler FSM. The foundation is completely solid: `validators.py`, `ocr_service.py`, `document_service.py`, `database.py`, and `models.py` are all implemented and tested. `main.py` has a stub with a comment saying "Bot Application setup goes here in Phase 5." `config.py` already defines `PERSISTENCE_PATH = STORAGE_DIR / "conversation_state.pkl"` — PicklePersistence is expected and the path is wired.

The dialog has 10 distinct collection states plus a confirmation state, and two passport-upload states, for a total of 12-13 states. The state machine flows linearly: GROUP → APARTMENT → CONTRACT_DATE → ACT_DATE → MONTHLY_AMOUNT → DEPOSIT_AMOUNT → DEPOSIT_METHOD → PHONE → EMAIL → PASSPORT_PAGE1 → PASSPORT_PAGE2 → CONFIRM → (end/restart). All handlers must be async. Document generation and DB save are deferred to Phase 6 (DOC-04 is Phase 6).

The critical architectural constraint is that Phase 5 delivers dialog collection and confirmation only — it does NOT call `generate_contract()` or `database.save_contract()`. Those calls are Phase 6's integration work. Phase 5 ends at the confirmation screen where the user approves OCR results and collected data.

**Primary recommendation:** Create `bot/handlers/conversation.py` with all ConversationHandler states wired to thin handler functions. Configure PicklePersistence from day one. Use integer state constants at module level. Call existing service functions directly — no new business logic belongs in this phase.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIAL-01 | User can select object group (Г39 or Г38) via inline keyboard | InlineKeyboardMarkup with two buttons; CallbackQueryHandler in GROUP state |
| DIAL-02 | User can select apartment number from list for selected group | Dynamic InlineKeyboardMarkup from APARTMENTS dict; CallbackQueryHandler in APARTMENT state |
| DIAL-03 | User can enter contract date in DD.MM.YYYY format | MessageHandler(filters.TEXT) + validate_date() in CONTRACT_DATE state |
| DIAL-04 | User can enter act date in DD.MM.YYYY format | MessageHandler(filters.TEXT) + validate_date() in ACT_DATE state |
| DIAL-05 | User can enter monthly rent amount | MessageHandler(filters.TEXT) + validate_amount() in MONTHLY_AMOUNT state |
| DIAL-06 | User can enter deposit amount | MessageHandler(filters.TEXT) + validate_amount() in DEPOSIT_AMOUNT state |
| DIAL-07 | User can choose deposit payment method (lump sum or 50%+50%) | InlineKeyboardMarkup with two buttons; CallbackQueryHandler in DEPOSIT_METHOD state |
| DIAL-08 | User can enter tenant phone in +7 XXX XXX XX XX format | MessageHandler(filters.TEXT) + validate_phone() in PHONE state |
| DIAL-09 | User can enter tenant email | MessageHandler(filters.TEXT) + validate_email() in EMAIL state |
| INFR-02 | /start command begins contract creation dialog | CommandHandler("start") as entry_point in ConversationHandler |
| INFR-03 | /cancel command cancels creation at any stage | CommandHandler("cancel") in fallbacks list; clears user_data |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Python 3.10+, python-telegram-bot 20.x (async) — CLAUDE.md specifies 20.x; installed version is 22.7 (fully compatible superset; use 22.x APIs)
- **All handlers must be async:** `async def handler(update, context)` — never synchronous
- **PicklePersistence from day one:** STATE.md roadmap decision — configure before any dialog state exists
- **Passport images required as document uploads, not photo type:** Prevents Telegram compression; handler must check for `document` type and warn on `photo` type (Phase 4 decision, applies to Phase 5 upload states)
- **No pydantic in validators:** Phase 2 decision — stdlib-only validators; callers use `isinstance(result, str)` for error detection
- **Result-style validator returns:** `validate_date()` returns `datetime.date | str`; str means error. Pattern: `result = validate_date(raw); if isinstance(result, str): await update.message.reply_text(result); return same_state`
- **concurrent_updates must be False:** Required when using ConversationHandler (PITFALLS.md Pitfall 4)
- **pyproject.toml:** `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorators needed in tests
- **Module import pattern:** Flat package (no `bot/` subdirectory yet) — all modules at project root: `config.py`, `validators.py`, `ocr_service.py`, `document_service.py`, `database.py`, `models.py`

---

## Standard Stack

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 22.7 | ConversationHandler FSM, PicklePersistence, Application | Already in requirements.txt; async-native |
| python-telegram-bot extras[job-queue] | 22.7 | Not needed for Phase 5 | — |

No new dependencies are required for Phase 5. All needed libraries are already installed.

### Key Classes from python-telegram-bot

| Class | Module | Purpose |
|-------|--------|---------|
| `Application` | `telegram.ext` | Central application object; receives persistence |
| `ApplicationBuilder` | `telegram.ext` | Fluent builder for Application; `.persistence()` method |
| `ConversationHandler` | `telegram.ext` | FSM router — maps states to handlers |
| `CommandHandler` | `telegram.ext` | Handles `/start`, `/cancel` |
| `MessageHandler` | `telegram.ext` | Handles text messages and document uploads |
| `CallbackQueryHandler` | `telegram.ext` | Handles inline keyboard button presses |
| `PicklePersistence` | `telegram.ext` | File-backed persistence for user_data + conversation state |
| `InlineKeyboardMarkup` | `telegram` | Inline keyboard layout |
| `InlineKeyboardButton` | `telegram` | Single button in inline keyboard |
| `filters` | `telegram.ext` | `filters.TEXT`, `filters.Document.ALL`, `filters.PHOTO`, `filters.ALL` |
| `ConversationHandler.END` | `telegram.ext` | Sentinel to terminate conversation |

### No New pip Installs Required

```bash
# All dependencies already satisfied by requirements.txt
# python-telegram-bot==22.7 is already installed
```

---

## Architecture Patterns

### Recommended File Structure for Phase 5

The existing project uses a flat module layout (all files at root). Phase 5 should follow the same pattern and introduce one new file:

```
rent-contract-bot/
├── bot/
│   └── handlers/
│       └── conversation.py   ← NEW: ConversationHandler + all state callbacks
├── config.py                 ← EXISTING: PERSISTENCE_PATH already defined
├── main.py                   ← MODIFY: wire ApplicationBuilder + ConversationHandler
├── validators.py             ← EXISTING: used directly in handlers
├── ocr_service.py            ← EXISTING: called in PASSPORT_PAGE2 state
├── document_service.py       ← EXISTING: NOT called in Phase 5 (Phase 6)
├── database.py               ← EXISTING: NOT called in Phase 5 (Phase 6)
├── models.py                 ← EXISTING: ContractData used at CONFIRM state
```

**Alternative (simpler):** Since the project uses flat layout, `conversation.py` could live at root level alongside other modules. Either approach works; the `bot/handlers/` nesting matches ARCHITECTURE.md's recommended structure. Planner can decide based on whether to start the nested structure now or defer to Phase 6.

### Pattern 1: State Constants as Module-Level Integers

```python
# conversation.py — top of file
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
```

**Why integers not strings:** ConversationHandler states dict uses integers as keys. String state names are a common beginner pattern that works but is slightly slower to look up and not idiomatic in PTB.

### Pattern 2: ConversationHandler Assembly

```python
# Source: official PTB docs + ARCHITECTURE.md
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

conv_handler = ConversationHandler(
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
            MessageHandler(filters.PHOTO, handle_passport_photo_warning),
        ],
        PASSPORT_PAGE2: [
            MessageHandler(filters.Document.ALL, handle_passport_page2),
            MessageHandler(filters.PHOTO, handle_passport_photo_warning),
        ],
        CONFIRM:        [CallbackQueryHandler(handle_confirm)],
    },
    fallbacks=[
        CommandHandler("cancel", cmd_cancel),
        MessageHandler(filters.ALL, handle_unexpected),
    ],
    name="contract_conversation",   # required for persistence
    persistent=True,                # required for persistence
    per_user=True,
    per_chat=True,
    allow_reentry=True,             # /start restarts even if mid-conversation
)
```

**Critical flags:**
- `name` and `persistent=True` are REQUIRED for PicklePersistence to save/restore this handler's state
- `allow_reentry=True` lets `/start` restart a stalled mid-conversation without first running `/cancel`

### Pattern 3: PicklePersistence in ApplicationBuilder

```python
# main.py
import config
from telegram.ext import Application, PicklePersistence

def main() -> None:
    config.validate()

    persistence = PicklePersistence(filepath=str(config.PERSISTENCE_PATH))

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .persistence(persistence)
        .concurrent_updates(False)   # REQUIRED with ConversationHandler
        .build()
    )

    from bot.handlers.conversation import build_conversation_handler
    app.add_handler(build_conversation_handler())

    _log.info("Bot starting, polling...")
    app.run_polling(drop_pending_updates=True)
```

**Why `drop_pending_updates=True`:** On restart, old messages queued during downtime are discarded. Without this, a restarted bot processes stale messages in wrong FSM states.

### Pattern 4: Thin Handler with Validator

The canonical pattern for all text-input states:

```python
async def handle_contract_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text
    result = validate_date(raw)
    if isinstance(result, str):           # error message
        await update.message.reply_text(result)
        return CONTRACT_DATE              # stay in same state
    context.user_data["contract_date"] = result
    await update.message.reply_text(
        "Введите дату Акта приёма-передачи (ДД.ММ.ГГГГ):"
    )
    return ACT_DATE
```

### Pattern 5: Inline Keyboard for Group Selection

```python
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()   # clean slate on /start
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Г39", callback_data="Г39"),
            InlineKeyboardButton("Г38", callback_data="Г38"),
        ]
    ])
    await update.message.reply_text(
        "Создание договора аренды.\nВыберите группу объектов:",
        reply_markup=keyboard,
    )
    return GROUP
```

### Pattern 6: Dynamic Apartment Keyboard

Apartment lists must be defined in config or conversation module. Г39 has 7 flats, Г38 has 8 flats (from REQUIREMENTS.md). The exact apartment numbers are not yet defined in any existing file — this is a gap the plan must address.

```python
APARTMENTS = {
    "Г39": ["39/1", "39/2", "39/3", "39/4", "39/5", "39/6", "39/7"],
    "Г38": ["38/1", "38/2", "38/3", "38/4", "38/5", "38/6", "38/7", "38/8"],
}

async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    group = query.data   # "Г39" or "Г38"
    context.user_data["group"] = group

    apartments = APARTMENTS[group]
    # Build 2-column keyboard
    buttons = [
        [InlineKeyboardButton(apt, callback_data=apt) for apt in apartments[i:i+4]]
        for i in range(0, len(apartments), 4)
    ]
    await query.edit_message_text(
        f"Группа {group}. Выберите квартиру:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return APARTMENT
```

### Pattern 7: Passport Upload — Document Type Required

Per PITFALLS.md (Pitfall 1) and STATE.md decision: accept documents, warn on photos.

```python
async def handle_passport_page1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    tg_file = await context.bot.get_file(doc.file_id)
    file_bytes = await tg_file.download_as_bytearray()
    context.user_data["passport_page1"] = bytes(file_bytes)
    await update.message.reply_text(
        "Страница 1 принята.\n"
        "Теперь отправьте страницу с пропиской как файл (Прикрепить → Файл):"
    )
    return PASSPORT_PAGE2

async def handle_passport_photo_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Пожалуйста, отправьте фото паспорта как *файл* (Прикрепить → Файл), "
        "а не как фотографию — иначе качество будет недостаточным для распознавания.",
        parse_mode="Markdown",
    )
    return PASSPORT_PAGE1  # or PASSPORT_PAGE2 depending on current state
```

**Problem:** A single `handle_passport_photo_warning` function cannot know which state it was called from without context. Use two separate warning handlers, or pass state via closure.

### Pattern 8: OCR in PASSPORT_PAGE2 Handler

Phase 4's `ocr_service.extract_passport_fields()` is called after both pages are collected:

```python
async def handle_passport_page2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    tg_file = await context.bot.get_file(doc.file_id)
    file_bytes = await tg_file.download_as_bytearray()
    context.user_data["passport_page2"] = bytes(file_bytes)

    await update.message.reply_text("Распознаю паспорт...")

    page1 = context.user_data["passport_page1"]
    page2 = context.user_data.get("passport_page2")

    fields = await ocr_service.extract_passport_fields(page1, page2)
    context.user_data["passport_fields"] = fields

    unclear = ocr_service.get_unclear_fields(fields)
    summary = ocr_service.format_ocr_summary(fields)

    if unclear:
        summary += f"\n\n⚠️ Нечитаемые поля: {', '.join(unclear)}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Подтвердить", callback_data="confirm"),
        InlineKeyboardButton("Переснять паспорт", callback_data="retry_passport"),
    ]])
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=keyboard)
    return CONFIRM
```

### Pattern 9: ContractData Assembly at CONFIRM

```python
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "retry_passport":
        context.user_data.pop("passport_page1", None)
        context.user_data.pop("passport_page2", None)
        context.user_data.pop("passport_fields", None)
        await query.edit_message_text("Отправьте фото первой страницы паспорта как файл:")
        return PASSPORT_PAGE1

    # query.data == "confirm"
    ud = context.user_data
    fields = ud["passport_fields"]

    # Validate age against contract_date
    tenant_dob = validate_date(fields["tenant_dob"])  # already a date string from OCR
    age_check = validate_age(tenant_dob, ud["contract_date"])
    if isinstance(age_check, str):
        await query.edit_message_text(f"Ошибка: {age_check}\nНачните заново: /start")
        return ConversationHandler.END

    contract_number = generate_contract_number(
        ud["group"], ud["apartment"], ud["contract_date"]
    )
    contract_data = ContractData(
        contract_number=contract_number,
        group=ud["group"],
        apartment=ud["apartment"],
        tenant_full_name=fields["tenant_full_name"],
        tenant_dob=tenant_dob,
        # ... all remaining fields ...
    )
    context.user_data["contract_data"] = contract_data

    await query.edit_message_text(
        "Данные подтверждены. Генерация договора..."
        # Phase 6: call generate_contract() and database.save_contract() here
    )
    return ConversationHandler.END
```

**Phase 5 scope boundary:** Phase 5 assembles ContractData and stores it in `user_data`. It does NOT call `generate_contract()` or `database.save_contract()`. Those are Phase 6. The CONFIRM handler ends the conversation after storing `contract_data`.

### Pattern 10: /cancel Handler

```python
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Создание договора отменено. Для начала введите /start"
    )
    return ConversationHandler.END
```

### Pattern 11: Unexpected Input Fallback

```python
async def handle_unexpected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Catch-all for unexpected message types in any state."""
    await update.message.reply_text(
        "Не понимаю этого сообщения. Следуйте инструкциям бота.\n"
        "Для отмены введите /cancel"
    )
    # Return None or don't return — PTB will keep the same state
    return None  # stays in current state
```

**Important:** Returning `None` from a fallback handler keeps the conversation in its current state. Do not return `ConversationHandler.END` from the unexpected-input handler.

### Anti-Patterns to Avoid

- **Returning the wrong state constant on validation failure:** Always return the SAME state (not the next state) when validation fails, so the user can retry.
- **Not filtering `~filters.COMMAND` in text handlers:** Without `filters.TEXT & ~filters.COMMAND`, typing `/cancel` mid-input triggers both the cancel handler AND the text validator, causing confusing behavior.
- **Storing passport bytes in user_data after OCR:** Passport image bytes are large and belong in-memory only during the session. After OCR completes, pop `passport_page1` and `passport_page2` from `user_data` to reduce PicklePersistence file size.
- **Not calling `await query.answer()`:** Every CallbackQueryHandler callback MUST call `await query.answer()` (even with empty string) within 10 seconds, or Telegram shows a spinning loading indicator on the button indefinitely.
- **Not editing the original message:** After a CallbackQuery, use `query.edit_message_text()` instead of `update.message.reply_text()` to replace the inline keyboard message rather than leaving it and sending a new one.
- **Using `context.user_data = {}` instead of `.clear()`:** The former replaces the dict with a new object; PicklePersistence still holds a reference to the old dict. Always use `context.user_data.clear()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine routing | Custom if/elif state dispatch | `ConversationHandler` from PTB | Built-in, battle-tested, handles edge cases like concurrent updates, per_user isolation |
| Session persistence | Custom pickle/JSON saving | `PicklePersistence` from PTB | Automatic; integrates with ApplicationBuilder; survives restart without extra code |
| Telegram polling loop | `bot.get_updates()` loop | `app.run_polling()` | Handles backoff, reconnection, exception isolation |
| Inline keyboard parsing | Custom button text parsing | `callback_data` field on `InlineKeyboardButton` | Clean separation of display text from machine-readable data |
| Conversation state enum | string-based states | Integer constants via `range(N)` | Idiomatic for PTB; avoids import issues between modules |
| Photo download | Raw HTTP calls | `await context.bot.get_file(file_id)` then `.download_as_bytearray()` | PTB handles auth headers and retry |

---

## Common Pitfalls

### Pitfall 1: PicklePersistence Not Configured — State Lost on Restart
**What goes wrong:** `ConversationHandler` without persistence resets all in-progress conversations when the bot restarts. User loses all entered data.
**Why it happens:** Default ConversationHandler has no backend.
**How to avoid:** Set `name="contract_conversation"` and `persistent=True` on ConversationHandler; pass `PicklePersistence(filepath=config.PERSISTENCE_PATH)` to `ApplicationBuilder.persistence()`.
**Warning signs:** Any bot implementation that does not call `.persistence()` before `.build()`.

### Pitfall 2: Missing `await query.answer()` in CallbackQueryHandlers
**What goes wrong:** Telegram client shows perpetual loading spinner on the button the user tapped. After 10 seconds, Telegram gives up and shows "query is too old" error.
**Why it happens:** Telegram requires acknowledgment of every callback query within 10 seconds.
**How to avoid:** First line of every CallbackQueryHandler callback must be `await query.answer()` or `await query.answer(text="optional toast message")`.
**Warning signs:** User sees spinning button; Telegram logs show `BadRequest: Query is too old`.

### Pitfall 3: Returning Same State vs. Wrong State on Validation Failure
**What goes wrong:** Handler returns `NEXT_STATE` even when validation fails, skipping the current input collection and advancing to the next step with a missing value. ContractData assembly fails with KeyError.
**How to avoid:** Pattern: `if isinstance(result, str): await update.message.reply_text(result); return CURRENT_STATE`
**Warning signs:** KeyError when assembling ContractData at CONFIRM; skipped fields in confirmation summary.

### Pitfall 4: Photo vs Document Upload Not Handled
**What goes wrong:** User sends passport as regular photo. Telegram compresses to JPEG with degraded quality. OCR fails or hallucinates fields.
**How to avoid:** Register `MessageHandler(filters.PHOTO, handle_passport_photo_warning)` alongside `MessageHandler(filters.Document.ALL, handle_passport_page1)` in PASSPORT_PAGE1 and PASSPORT_PAGE2 states.
**Warning signs:** `update.message.photo` is set instead of `update.message.document`; OCR returns multiple UNCLEAR fields.

### Pitfall 5: `filters.TEXT` Without `~filters.COMMAND`
**What goes wrong:** User types `/cancel` in a text-input state. The text handler fires BEFORE the cancel command handler, attempting to validate "/cancel" as a date, amount, or phone number.
**How to avoid:** Use `filters.TEXT & ~filters.COMMAND` in all MessageHandler registrations for text states.
**Warning signs:** `/cancel` returns a validation error message instead of cancelling.

### Pitfall 6: `concurrent_updates` Not Set to False
**What goes wrong:** PTB default allows concurrent processing. With ConversationHandler, two simultaneous updates from the same user can corrupt `user_data`.
**How to avoid:** `.concurrent_updates(False)` in ApplicationBuilder chain.
**Warning signs:** Race condition corrupts `user_data` keys; state machine jumps states unpredictably.

### Pitfall 7: Apartment Numbers Not Defined Anywhere in Codebase
**What goes wrong:** Phase 5 needs the actual apartment list for Г39 (7 units) and Г38 (8 units). Currently no file defines these. The inline keyboard cannot be built without them.
**How to avoid:** Define `APARTMENTS` dict in `conversation.py` or add to `config.py`. This is a data gap that must be resolved in the plan — get exact apartment identifiers from the project owner, or use placeholder numbers (1-7 for Г39, 1-8 for Г38).
**Warning signs:** The REQUIREMENTS.md says "7 flats" and "8 flats" but specifies no apartment numbers/identifiers.

### Pitfall 8: OCR Fields Are Strings — Date Parsing Required
**What goes wrong:** `ocr_service.extract_passport_fields()` returns all 10 fields as strings, including `tenant_dob` and `passport_issued_date` in "ДД.ММ.ГГГГ" format. ContractData expects `datetime.date` objects for these fields. Missing the conversion step causes a TypeError when constructing ContractData.
**How to avoid:** In the CONFIRM handler, call `validate_date(fields["tenant_dob"])` to convert the OCR string to a `datetime.date`. If validate_date returns an error string (malformed OCR output), report to user and return PASSPORT_PAGE1.
**Warning signs:** `TypeError: expected datetime.date, got str` when constructing ContractData.

### Pitfall 9: Deposit Method State Requires Amount Already in user_data
**What goes wrong:** The DEPOSIT_METHOD state (50%+50% or lump sum) needs to show the deposit half-amount in the button labels or confirmation message. If `deposit_amount` is not yet stored when DEPOSIT_METHOD is displayed, the display is wrong.
**How to avoid:** Store `deposit_amount` in `user_data` in the DEPOSIT_AMOUNT handler BEFORE transitioning to DEPOSIT_METHOD. Then read `context.user_data["deposit_amount"]` to compute the half in the deposit method keyboard.

---

## Code Examples

### Full ConversationHandler Registration

```python
# Source: ARCHITECTURE.md Pattern 1 + official PTB ConversationHandler docs

def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            GROUP: [CallbackQueryHandler(handle_group)],
            APARTMENT: [CallbackQueryHandler(handle_apartment)],
            CONTRACT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_date)],
            ACT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_act_date)],
            MONTHLY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_monthly_amount)],
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deposit_amount)],
            DEPOSIT_METHOD: [CallbackQueryHandler(handle_deposit_method)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            PASSPORT_PAGE1: [
                MessageHandler(filters.Document.ALL, handle_passport_page1),
                MessageHandler(filters.PHOTO, handle_passport_photo_warning_p1),
            ],
            PASSPORT_PAGE2: [
                MessageHandler(filters.Document.ALL, handle_passport_page2),
                MessageHandler(filters.PHOTO, handle_passport_photo_warning_p2),
            ],
            CONFIRM: [CallbackQueryHandler(handle_confirm)],
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
```

### ApplicationBuilder with PicklePersistence

```python
# Source: PTB wiki "Making your bot persistent" + config.py PERSISTENCE_PATH

persistence = PicklePersistence(filepath=str(config.PERSISTENCE_PATH))
app = (
    Application.builder()
    .token(config.BOT_TOKEN)
    .persistence(persistence)
    .concurrent_updates(False)
    .build()
)
```

### Validation Error Re-prompt Pattern

```python
# Used in all text-input states. Source: ARCHITECTURE.md Pattern, validators.py

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = validate_phone(update.message.text)
    if isinstance(result, str):
        await update.message.reply_text(result)  # Russian error from validators.py
        return PHONE  # stay in same state
    context.user_data["tenant_phone"] = result
    await update.message.reply_text("Введите email арендатора:")
    return EMAIL
```

---

## State Machine Map

```
/start
  │
  ▼
GROUP ──── callback "Г39"/"Г38" ──────────────────────────────┐
  │                                                             │
  ▼                                                             │
APARTMENT ── callback apt_id ──────────────────────────────────┤
  │                                                             │
  ▼                                                             │
CONTRACT_DATE ── text ── validate_date() ──── error → stay ──┤
  │                                                             │
  ▼                                                             │
ACT_DATE ── text ── validate_date() ──── error → stay ────────┤
  │                                                             │
  ▼                                                             │
MONTHLY_AMOUNT ── text ── validate_amount() ─── error → stay ─┤
  │                                                             │
  ▼                                                             │
DEPOSIT_AMOUNT ── text ── validate_amount() ─── error → stay ─┤
  │                                                             │
  ▼                                                             │
DEPOSIT_METHOD ── callback "lump"/"split" ────────────────────┤
  │                                                             │
  ▼                                                             │
PHONE ── text ── validate_phone() ──── error → stay ──────────┤
  │                                                             │
  ▼                                                             │
EMAIL ── text ── validate_email() ──── error → stay ──────────┤
  │                                                             │
  ▼                                                             │
PASSPORT_PAGE1 ── document ──────────────────────────────────┤
             └──── photo ── warn → stay ─────────────────────┤
  │                                                             │
  ▼                                                             │
PASSPORT_PAGE2 ── document ── OCR call ──────────────────────┤
             └──── photo ── warn → stay ─────────────────────┤
  │                                                             │
  ▼                                                             │
CONFIRM ── callback "confirm" ── assemble ContractData ── END ┤
       └── callback "retry_passport" ────────────────── PASSPORT_PAGE1
  │                                                             │
  ▼                                                             │
/cancel (any state) ── clear user_data ── END ◄───────────────┘
```

---

## Open Questions

1. **Exact apartment identifiers for Г39 and Г38**
   - What we know: Г39 has 7 flats, Г38 has 8 flats (REQUIREMENTS.md)
   - What's unclear: The actual apartment numbers/names displayed to the user and stored in ContractData. The contract number format is "Г39/42/..." suggesting actual apartment numbers, not sequential 1-7.
   - Recommendation: Planner should request clarification or use placeholder numbers (1-7, 1-8) with a TODO comment. The APARTMENTS dict should be in `config.py` for easy modification.

2. **Phase 5 vs Phase 6 scope boundary at CONFIRM**
   - What we know: DOC-04 (send PDF) is Phase 6. Phase 5 ends at CONFIRM.
   - What's unclear: Should Phase 5's CONFIRM handler leave the conversation in END state with a "Generating contract..." placeholder, or produce no message after confirmation since generation is not wired yet?
   - Recommendation: Phase 5 ends CONFIRM with "Данные подтверждены. Договор будет сгенерирован (Phase 6)." The CONFIRM handler stores `contract_data` in `user_data` and returns `ConversationHandler.END`. Phase 6 will replace this message with the actual generation call.

3. **Warning handler for photo in PASSPORT_PAGE2 — same function or separate?**
   - What we know: The photo warning message is the same for both passport pages.
   - What's unclear: Can one function serve both states?
   - Recommendation: Define two functions (`handle_passport_photo_warning_p1` returning `PASSPORT_PAGE1`, `handle_passport_photo_warning_p2` returning `PASSPORT_PAGE2`) or use a closure factory. Two explicit functions are clearer.

---

## Environment Availability

All required tools are already installed and verified by prior phases.

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| python-telegram-bot 22.7 | ConversationHandler, PicklePersistence | ✓ | In requirements.txt, installed Phase 1 |
| Python 3.10+ | Async syntax, match statements | ✓ | Verified Phase 1 |
| pytest + pytest-asyncio | Test suite | ✓ | In requirements-dev.txt, asyncio_mode=auto |
| All service modules | conversation.py imports | ✓ | validators.py, ocr_service.py, document_service.py, database.py all complete |

Step 2.6: No new external dependencies. All required libraries are already installed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_conversation.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIAL-01 | Group keyboard shows Г39 and Г38 buttons | unit (mocked PTB) | `pytest tests/test_conversation.py::TestGroupSelection -x` | ❌ Wave 0 |
| DIAL-02 | Apartment keyboard shows correct count per group | unit (mocked PTB) | `pytest tests/test_conversation.py::TestApartmentSelection -x` | ❌ Wave 0 |
| DIAL-03 | Contract date validated; invalid stays in state | unit (validator already tested) | `pytest tests/test_conversation.py::TestContractDate -x` | ❌ Wave 0 |
| DIAL-04 | Act date validated; invalid stays in state | unit | `pytest tests/test_conversation.py::TestActDate -x` | ❌ Wave 0 |
| DIAL-05 | Monthly amount validated; invalid stays in state | unit | `pytest tests/test_conversation.py::TestMonthlyAmount -x` | ❌ Wave 0 |
| DIAL-06 | Deposit amount validated; invalid stays in state | unit | `pytest tests/test_conversation.py::TestDepositAmount -x` | ❌ Wave 0 |
| DIAL-07 | Deposit method keyboard shows two options | unit | `pytest tests/test_conversation.py::TestDepositMethod -x` | ❌ Wave 0 |
| DIAL-08 | Phone validated; invalid stays in state | unit | `pytest tests/test_conversation.py::TestPhone -x` | ❌ Wave 0 |
| DIAL-09 | Email validated; invalid stays in state | unit | `pytest tests/test_conversation.py::TestEmail -x` | ❌ Wave 0 |
| INFR-02 | /start sends group selection keyboard | unit | `pytest tests/test_conversation.py::TestStart -x` | ❌ Wave 0 |
| INFR-03 | /cancel clears user_data and returns END | unit | `pytest tests/test_conversation.py::TestCancel -x` | ❌ Wave 0 |

**Testing approach for PTB handlers:** python-telegram-bot handlers are async functions that take `(Update, ContextTypes.DEFAULT_TYPE)` as parameters. Testing them in isolation requires constructing mock `Update` and `Context` objects. The standard pattern is:

```python
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User, Message, Chat

def make_text_update(text: str) -> Update:
    user = User(id=1, first_name="Test", is_bot=False)
    chat = Chat(id=1, type="private")
    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()
    message.from_user = user
    message.chat = chat
    update = MagicMock(spec=Update)
    update.message = message
    update.callback_query = None
    return update

def make_context() -> MagicMock:
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    return context
```

### Sampling Rate

- **Per task commit:** `pytest tests/test_conversation.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_conversation.py` — covers all DIAL-* and INFR-02/03 requirements
- [ ] Mock Update/Context helper fixtures in `tests/fixtures/` or `tests/conftest.py`

*(Existing test infrastructure covers validators, database, document_service, and ocr_service. Only the conversation handler test file is missing.)*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Updater` class | `ApplicationBuilder` | PTB v20 (2022) | Simpler setup; Updater removed in v22 |
| Synchronous handlers | `async def` handlers | PTB v20 (2022) | All handlers must be async; no blocking calls |
| `ConversationHandler` with string states | Integer constants via `range(N)` | Always standard | Integers are faster dict keys; conventional |
| `bot.send_message()` (raw) | `update.message.reply_text()` | PTB v13+ | Reply context; no need to pass chat_id manually |

**Deprecated:**
- `Updater` class: removed/deprecated in v22; use `Application` + `run_polling()`
- `context.dispatcher`: replaced by `application` in v20+
- `ConversationHandler.WAITING`: use explicit state integers

---

## Sources

### Primary (HIGH confidence)
- `validators.py` (project codebase) — validator signatures, error return pattern
- `ocr_service.py` (project codebase) — `extract_passport_fields()`, `get_unclear_fields()`, `format_ocr_summary()` APIs
- `document_service.py` (project codebase) — `generate_contract_number()` signature
- `database.py` (project codebase) — `save_contract()` API, `init()` call pattern
- `models.py` (project codebase) — `ContractData` all fields and types
- `config.py` (project codebase) — `PERSISTENCE_PATH`, `BOT_TOKEN`, `APARTMENTS` gap identified
- `.planning/research/PITFALLS.md` — Pitfalls 1, 4, 11 directly apply
- `.planning/research/ARCHITECTURE.md` — Pattern 1 (FSM), Pattern 2 (user_data), Pattern 3 (thin handlers)
- `.planning/research/STACK.md` — python-telegram-bot 22.7 ConversationHandler patterns
- `pyproject.toml` — `asyncio_mode = "auto"` confirmed

### Secondary (MEDIUM confidence)
- [PTB Wiki: Making your bot persistent](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent) — PicklePersistence setup verified in prior research
- [ConversationHandler official docs v22](https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html) — `name`, `persistent`, `allow_reentry` flags

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all existing code inspected directly
- Architecture: HIGH — four completed service modules inspected; APIs confirmed
- Pitfalls: HIGH — built from PITFALLS.md (prior verified research) + code inspection
- Apartment numbers: LOW — count known (7+8), exact identifiers not found in any file

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (python-telegram-bot 22.x is stable; no breaking changes expected)
