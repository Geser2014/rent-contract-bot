---
phase: 05-fsm-dialog-layer
verified: 2026-03-24T09:00:00Z
status: passed
score: 16/16 must-haves verified
re_verification: false
---

# Phase 05: FSM Dialog Layer Verification Report

**Phase Goal:** A user can navigate the complete contract creation dialog from group selection through confirmation, with all inputs validated inline and the ability to cancel at any point
**Verified:** 2026-03-24T09:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Sending /start presents a Г39 / Г38 inline keyboard | VERIFIED | `cmd_start` calls `context.user_data.clear()`, builds 2-button inline keyboard, replies, returns `GROUP` (0). Test `test_cmd_start_returns_group_state` passes. |
| 2 | Tapping Г39 shows apartment inline keyboard for that group | VERIFIED | `handle_group` reads `query.data`, stores in `user_data["group"]`, builds rows-of-4 keyboard from `APARTMENTS[group]`, calls `edit_message_text`, returns `APARTMENT` (1). Test `test_handle_group_stores_group_and_returns_apartment` passes. |
| 3 | Entering an invalid date returns a Russian error and stays in the same state | VERIFIED | `handle_contract_date` uses `isinstance(result, str)` pattern; replies with error string and returns `CONTRACT_DATE`. Test `test_handle_contract_date_invalid` passes with assertion `result == CONTRACT_DATE` and `"contract_date" not in ctx.user_data`. |
| 4 | Entering a valid date advances to the next state and stores the value in user_data | VERIFIED | `handle_contract_date` stores `datetime.date` in `user_data["contract_date"]` and returns `ACT_DATE`. Test `test_handle_contract_date_valid` asserts `ctx.user_data["contract_date"] == datetime.date(2024, 3, 15)`. |
| 5 | Photo upload at PASSPORT_PAGE1 or PASSPORT_PAGE2 returns a warning and keeps the same state | VERIFIED | `handle_passport_photo_warning_p1` returns `PASSPORT_PAGE1` (9); `handle_passport_photo_warning_p2` returns `PASSPORT_PAGE2` (10). Both reply with a Markdown warning. Tests pass. |
| 6 | Document upload at PASSPORT_PAGE1 stores bytes and advances to PASSPORT_PAGE2 | VERIFIED | `handle_passport_page1` downloads via `context.bot.get_file()`, stores `bytes` in `user_data["passport_page1"]`, returns `PASSPORT_PAGE2`. Both document and photo handlers are registered for `PASSPORT_PAGE1` state. |
| 7 | After both passport pages are uploaded, OCR is called and a summary with confirm/retry keyboard is shown | VERIFIED | `handle_passport_page2` calls `ocr_service.extract_passport_fields()`, calls `ocr_service.format_ocr_summary()`, pops bytes from `user_data`, builds confirm/retry keyboard, returns `CONFIRM`. UNCLEAR fields appended to summary if present. |
| 8 | Confirming valid OCR data assembles ContractData in user_data and ends the conversation | VERIFIED | `handle_confirm` on `query.data == "confirm"` parses OCR dates via `validate_date`, checks age via `validate_age`, calls `generate_contract_number`, constructs `ContractData(...)` with all 19 fields, stores in `user_data["contract_data"]`, returns `ConversationHandler.END`. |
| 9 | Sending /cancel at any state clears user_data and sends a cancellation message | VERIFIED | `cmd_cancel` calls `context.user_data.clear()`, replies with cancellation message, returns `ConversationHandler.END`. Registered in `fallbacks`. Test `test_cmd_cancel_clears_user_data_and_ends` passes with `ctx.user_data == {}`. |
| 10 | Unexpected input (sticker, voice, etc.) triggers a helpful re-prompt without advancing state | VERIFIED | `handle_unexpected` replies with re-prompt message, returns `None` (not `ConversationHandler.END`). Registered in `fallbacks` as `MessageHandler(filters.ALL, ...)`. Test `test_handle_unexpected_returns_none` asserts `result is None`. |
| 11 | python main.py starts the bot with PicklePersistence configured and ConversationHandler registered | VERIFIED | `main.py` builds `PicklePersistence(filepath=str(config.PERSISTENCE_PATH))`, chains `.token().persistence().concurrent_updates(False).build()`, calls `app.add_handler(build_conversation_handler())`, calls `app.run_polling(drop_pending_updates=True)`. File parses without errors. |
| 12 | PicklePersistence uses config.PERSISTENCE_PATH (storage/conversation_state.pkl) | VERIFIED | `main.py` line 20: `PicklePersistence(filepath=str(config.PERSISTENCE_PATH))`. |
| 13 | ApplicationBuilder sets concurrent_updates=False (required for ConversationHandler) | VERIFIED | `main.py` line 25: `.concurrent_updates(False)`. |
| 14 | Unit tests confirm /cancel clears user_data and returns ConversationHandler.END | VERIFIED | `test_cmd_cancel_clears_user_data_and_ends` — asserts both conditions. Passes. |
| 15 | Unit tests confirm invalid date input stays in CONTRACT_DATE state and returns error string | VERIFIED | `test_handle_contract_date_invalid` — asserts `result == CONTRACT_DATE` and error reply sent. Passes. |
| 16 | Unit tests confirm valid group callback stores group in user_data and returns APARTMENT state | VERIFIED | `test_handle_group_stores_group_and_returns_apartment` — asserts `ctx.user_data["group"] == "Г39"` and `result == APARTMENT`. Passes. |

**Score:** 16/16 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `bot/__init__.py` | Package marker for bot/ directory | VERIFIED | File exists, `bot/` is importable. |
| `bot/handlers/__init__.py` | Package marker for bot/handlers/ directory | VERIFIED | File exists, `bot.handlers` is importable. |
| `bot/handlers/conversation.py` | All FSM state handlers, `build_conversation_handler()` factory | VERIFIED | 426 lines; exports all 12 state constants, 14 handler functions, `APARTMENTS` dict, `build_conversation_handler`. Parses without errors. |
| `main.py` | Bot entry point with ApplicationBuilder, PicklePersistence, ConversationHandler wired | VERIFIED | 35 lines; all 5 required wiring elements present. Parses without errors. |
| `tests/test_conversation.py` | Unit tests for conversation handler state transitions (min 60 lines) | VERIFIED | 233 lines; 13 test functions, all pass. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `bot/handlers/conversation.py` | `validators.py` | `from validators import validate_age, validate_amount, validate_date, validate_email, validate_phone` | WIRED | Line 23 — all 5 validators imported and called in handlers. |
| `bot/handlers/conversation.py` | `ocr_service.py` | `import ocr_service` | WIRED | Line 20 — `ocr_service.extract_passport_fields`, `get_unclear_fields`, `format_ocr_summary` all called in `handle_passport_page2`. |
| `bot/handlers/conversation.py` | `models.py` | `ContractData(...)` construction in `handle_confirm` | WIRED | Lines 332-353 — `ContractData` constructed with all 19 fields from `user_data` and OCR `fields` dict. |
| `bot/handlers/conversation.py` | `document_service.py` | `generate_contract_number` call in `handle_confirm` | WIRED | Line 329 — `generate_contract_number(ud["group"], ud["apartment"], ud["contract_date"])` called before `ContractData` assembly. |
| `main.py` | `bot/handlers/conversation.py` | `build_conversation_handler()` called after `ApplicationBuilder.build()` | WIRED | Lines 10, 28 — imported and called: `app.add_handler(build_conversation_handler())`. |
| `main.py` | `config.py` | `config.PERSISTENCE_PATH` passed to `PicklePersistence` | WIRED | Line 20 — `PicklePersistence(filepath=str(config.PERSISTENCE_PATH))`. |

---

### Data-Flow Trace (Level 4)

Not applicable. This phase produces an FSM dialog handler, not a component that renders dynamic data from a database. All data flows through Telegram's `context.user_data` dict during an active conversation session. The data-flow is exercised end-to-end in the unit tests.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `build_conversation_handler()` returns 12-state ConversationHandler | `python -c "from bot.handlers.conversation import build_conversation_handler; h = build_conversation_handler(); assert len(h.states) == 12; print('OK')"` | OK | PASS |
| conversation.py parses without syntax errors | `python -c "import ast; ast.parse(open('bot/handlers/conversation.py').read()); print('OK')"` | OK | PASS |
| main.py parses without syntax errors | `python -c "import ast; ast.parse(open('main.py').read()); print('OK')"` | OK | PASS |
| All 13 conversation unit tests pass | `python -m pytest tests/test_conversation.py -v` | 13 passed in 0.94s | PASS |
| Full test suite (70 tests) passes with no regressions | `python -m pytest tests/ -v` | 70 passed, 1 skipped in 1.29s | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| DIAL-01 | 05-01 | Выбор группы объектов (Г39 или Г38) через inline-клавиатуру | SATISFIED | `cmd_start` + `handle_group` — GROUP state with inline keyboard. `APARTMENTS` dict has both groups. |
| DIAL-02 | 05-01 | Выбор номера квартиры из списка | SATISFIED | `handle_apartment` — APARTMENT state with dynamic keyboard from `APARTMENTS[group]`. |
| DIAL-03 | 05-01 | Ввод даты договора в формате ДД.ММ.ГГГГ | SATISFIED | `handle_contract_date` — CONTRACT_DATE state with `validate_date` and isinstance error detection. |
| DIAL-04 | 05-01 | Ввод даты Акта приёма-передачи | SATISFIED | `handle_act_date` — ACT_DATE state. |
| DIAL-05 | 05-01 | Ввод суммы ежемесячной аренды | SATISFIED | `handle_monthly_amount` — MONTHLY_AMOUNT state with `validate_amount`. |
| DIAL-06 | 05-01 | Ввод суммы депозита | SATISFIED | `handle_deposit_amount` — DEPOSIT_AMOUNT state. |
| DIAL-07 | 05-01 | Выбор способа внесения депозита (единовременно или 50%+50%) | SATISFIED | `handle_deposit_method` — DEPOSIT_METHOD state with two-button callback keyboard. Half amount computed from `user_data`. |
| DIAL-08 | 05-01 | Ввод телефона арендатора | SATISFIED | `handle_phone` — PHONE state using `validate_phone` + `re.fullmatch` success detection. Bug-fixed in Plan 02. |
| DIAL-09 | 05-01 | Ввод email арендатора | SATISFIED | `handle_email` — EMAIL state using `validate_email` + `re.fullmatch` success detection. Bug-fixed in Plan 02. |
| INFR-02 | 05-02 | Команда /start начинает диалог создания договора | SATISFIED | `build_conversation_handler` entry_points: `CommandHandler("start", cmd_start)`. ConversationHandler registered in `main.py` via `app.add_handler()`. |
| INFR-03 | 05-01, 05-02 | Команда /cancel отменяет создание на любом этапе | SATISFIED | `cmd_cancel` in `fallbacks` list of ConversationHandler — catches /cancel at any state. Tested in `test_cmd_cancel_clears_user_data_and_ends`. |

**All 11 requirement IDs from phase plans accounted for.** No orphaned requirements.

Note: Phase 05 plans do not claim VALD-06 (error reprompt) as a formal ID, but the inline validation behavior (reply error + stay in state) is directly implemented across all 6 text-input handlers, satisfying the intent even though VALD-06 is formally owned by Phase 2.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `bot/handlers/conversation.py` | PTBUserWarning on `ConversationHandler` construction re: `per_message=False` | Info | Advisory from python-telegram-bot library; `per_message=False` is the correct setting for per-user conversation tracking (not per-message). No action needed; documented in SUMMARY as expected. |

No TODO/FIXME/placeholder comments found. No empty return stubs. No `context.user_data = {}` anti-pattern. No `filters.TEXT` without `& ~filters.COMMAND`. All `CallbackQueryHandler` callbacks call `await query.answer()` (4 occurrences verified). Passport bytes are popped from `user_data` after OCR (2 pop calls verified).

---

### Human Verification Required

#### 1. End-to-end Telegram dialog flow

**Test:** Connect bot to a real Telegram token, send /start, complete all 12 states from group selection through passport upload and confirmation.
**Expected:** Bot responds at each state, invalid inputs are rejected with Russian error messages, valid inputs advance the state, /cancel clears the session from any step.
**Why human:** Requires a live Telegram Bot token and actual file uploads; cannot be simulated programmatically.

#### 2. PicklePersistence survives bot restart

**Test:** Start bot, begin a conversation (reach CONTRACT_DATE state), stop bot, restart bot, send a message in the same chat.
**Expected:** Bot resumes from CONTRACT_DATE state (not restarting from scratch) because PicklePersistence restored `user_data` and FSM state from disk.
**Why human:** Requires bot restart with a live token; cannot be tested statically.

#### 3. Deposit method keyboard display

**Test:** Enter a valid deposit amount (e.g., 60000), check the inline keyboard displayed.
**Expected:** Two buttons visible: "Единовременно" and "50%+50% (30000р + 30000р)" showing correct half-amount calculation.
**Why human:** Keyboard rendering requires Telegram client; half-amount display cannot be visually verified programmatically.

---

### Gaps Summary

No gaps. All 16 must-have truths verified. All 5 artifacts exist and are substantive. All 6 key links are wired. All 11 requirement IDs are satisfied. 70 tests pass with no regressions. One notable finding: a bug in `handle_phone` and `handle_email` (both validators return `str` for both success and error, making `isinstance` check always true) was discovered and fixed during Plan 02 — the fix uses `re.fullmatch` pattern matching to distinguish valid output from error strings. This bug would have blocked DIAL-08 and DIAL-09 from functioning; it is resolved and verified by tests.

---

_Verified: 2026-03-24T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
