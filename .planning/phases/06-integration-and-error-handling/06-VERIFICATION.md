---
phase: 06-integration-and-error-handling
verified: 2026-03-24T10:00:00Z
status: passed
score: 8/8 must-haves verified
gaps: []
human_verification:
  - test: "End-to-end Telegram delivery"
    expected: "After confirming OCR data the bot sends a PDF document in the same Telegram chat with caption 'Договор аренды №... готов.'"
    why_human: "Requires a live bot token, LibreOffice installed, and an actual Telegram conversation — cannot be exercised without running infrastructure"
---

# Phase 6: Integration and Error Handling — Verification Report

**Phase Goal:** All layers are wired together in main.py and the complete contract cycle runs end-to-end: group selection through PDF delivered in Telegram, with all external failures handled gracefully
**Verified:** 2026-03-24T10:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After user confirms OCR data, the bot generates a PDF contract and sends it as a Telegram document in the same chat | VERIFIED | `handle_confirm` calls `await generate_contract(contract_data)`, then `context.bot.send_document(...)` — lines 380, 415-420 of conversation.py |
| 2 | The bot replies with the contract number and a success message before sending the document | VERIFIED | `query.edit_message_text(f"Данные подтверждены. Номер договора: {contract_number}\nГенерирую договор... ⏳")` at line 373-376 |
| 3 | The database record for the contract contains the correct pdf_path after generation | VERIFIED | `contract_data.pdf_path = pdf_path` (line 396) is set before `await database.save_contract(contract_data)` (line 401) |
| 4 | database.init() is called at bot startup so the contracts table exists before any save | VERIFIED | `_post_init` async function (main.py lines 17-19) calls `await database.init()` and is registered via `.post_init(_post_init)` in the ApplicationBuilder chain (line 32) |
| 5 | A Claude Vision API failure in handle_passport_page2 surfaces a user-readable Russian message and returns to PASSPORT_PAGE1 state — the bot does not crash | VERIFIED | `except (anthropic.APIError, ValueError)` at line 250, sends "Не удалось распознать паспорт..." and returns `PASSPORT_PAGE1` (lines 250-258) |
| 6 | A LibreOffice PDF conversion failure in handle_confirm surfaces a user-readable Russian message and returns ConversationHandler.END — no orphan temp files remain | VERIFIED | `except subprocess.TimeoutExpired` (line 381) and `except (FileNotFoundError, RuntimeError)` (line 388) both clear user_data, send Russian message, return `ConversationHandler.END` |
| 7 | A database IntegrityError (duplicate contract number) in handle_confirm surfaces a user-readable message instead of an unhandled exception | VERIFIED | `except IntegrityError` at line 402, sends "Договор с таким номером уже существует..." via `send_message` and returns `ConversationHandler.END` |
| 8 | After any handled error the bot continues to receive and respond to new /start commands | VERIFIED | All error handlers return a valid state (PASSPORT_PAGE1 or ConversationHandler.END) — the ConversationHandler FSM remains intact; `allow_reentry=True` is set in `build_conversation_handler()` |

**Score:** 8/8 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `main.py` | database.init() called before app.run_polling() | VERIFIED | `_post_init` defined at lines 17-19, registered at line 32 with `.post_init(_post_init)` |
| `bot/handlers/conversation.py` | handle_confirm with generate_contract + save_contract + send_document wired in; try/except blocks around all three external calls | VERIFIED | All three calls present with proper error boundaries at lines 379-423 |
| `tests/test_integration.py` | 6 unit tests for all error boundaries | VERIFIED | File exists, 6 async test functions present, all 6 pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py` | `database.init` | `_post_init` hook registered with `.post_init()` | WIRED | `await database.init()` at line 19; `.post_init(_post_init)` at line 32 |
| `handle_confirm` | `document_service.generate_contract` | `await generate_contract(contract_data)` | WIRED | Line 380; import at line 26 |
| `handle_confirm` | `database.save_contract` | `await database.save_contract(contract_data)` | WIRED | Line 401; `import database` at line 25 |
| `handle_confirm` | `context.bot.send_document` | `await context.bot.send_document(chat_id, document=pdf_file, ...)` | WIRED | Lines 415-420 |
| `handle_passport_page2` | `ocr_service.extract_passport_fields` | `try/except (anthropic.APIError, ValueError)` | WIRED | Line 250; returns PASSPORT_PAGE1 on failure |
| `handle_confirm generate_contract call` | `document_service.generate_contract` | `try/except FileNotFoundError, RuntimeError, subprocess.TimeoutExpired` | WIRED | Lines 381-394 |
| `handle_confirm save_contract call` | `database.save_contract` | `try/except IntegrityError` | WIRED | Lines 402-409 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `handle_confirm` | `pdf_path` | `await generate_contract(contract_data)` returns absolute path string from LibreOffice | Yes — document_service runs LibreOffice subprocess and returns the output PDF path | FLOWING |
| `handle_confirm` | `contract_data` | Assembled from `context.user_data` fields set through FSM states | Yes — all fields required (group, apartment, dates, amounts, passport_fields) come from user dialog | FLOWING |
| `database.save_contract` | `contract_data.pdf_path` | Set at line 396 before save at line 401 | Yes — the actual filesystem path is committed to DB before the DB call | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Both files parse cleanly | `python -c "import ast; ast.parse(open('main.py').read()); ast.parse(open('bot/handlers/conversation.py').read()); print('both files parse cleanly')"` | `both files parse cleanly` | PASS |
| 6 integration tests pass | `python -m pytest tests/test_integration.py -v` | `6 passed in 0.93s` | PASS |
| Full suite (76 tests) passes with no regressions | `python -m pytest tests/ -v --tb=short` | `76 passed, 1 skipped in 1.29s` (skipped = LibreOffice integration test, expected on dev) | PASS |
| 4 Russian error messages present in conversation.py | `grep -n "распознать паспорт\|долго\|Не удалось создать\|уже существует" bot/handlers/conversation.py` | 4 matching lines (lines 255, 385, 392, 407) | PASS |
| 4 logger.error calls present (one per error boundary) | `grep -n "logger.error" bot/handlers/conversation.py` | Lines 251, 382, 389, 403 | PASS |
| database.init wired in main.py | `grep -n "post_init\|database.init" main.py` | Lines 17, 19, 32 | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DOC-04 | 06-01-PLAN.md | Система отправляет готовый PDF в Telegram-чат как документ | SATISFIED | `context.bot.send_document(...)` called in `handle_confirm` after successful PDF generation; `test_happy_path_confirm` confirms `send_document` is called |
| INFR-05 | 06-02-PLAN.md | Ошибки в критических операциях перехватываются и пользователь получает понятное сообщение | SATISFIED | Three try/except blocks cover all three critical operation types: OCR (anthropic.APIError, ValueError), PDF (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError), DB (IntegrityError); all return Russian messages; 5 error-path tests pass |

Both requirements traced in REQUIREMENTS.md traceability table as Phase 6 / Complete.

No orphaned requirements found — no additional Phase 6 requirement IDs appear in REQUIREMENTS.md beyond DOC-04 and INFR-05.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Checked for: TODO/FIXME/PLACEHOLDER comments, `return null`/`return {}`, empty handlers, stub returns, hardcoded empty data. None present in the modified files. The previously stubbed `handle_confirm` tail ("Генерация договора будет выполнена в следующем шаге.") has been fully replaced with the real pipeline.

---

## Human Verification Required

### 1. End-to-End Telegram Delivery

**Test:** Configure `.env` with a valid `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY`, ensure LibreOffice headless is installed, run `python main.py`, start a conversation with `/start`, complete the full dialog including passport photo upload, click "Подтвердить", and observe the bot response.

**Expected:** The bot edits the message to show "Данные подтверждены. Номер договора: .../... Генерирую договор... ⏳", then delivers a PDF document file in the chat with caption "Договор аренды №... готов."

**Why human:** Requires live bot token, LibreOffice installed on the test machine, a real or mock Telegram message with a valid photo document, and interaction with the Anthropic API for OCR. Cannot be automated without running infrastructure.

---

## Gaps Summary

No gaps found. All eight observable truths are verified, all artifacts exist and are substantive and wired, all key links are confirmed in the actual codebase, and both requirement IDs (DOC-04, INFR-05) are fully satisfied with passing tests.

The one item routed to human verification (live end-to-end delivery) is expected for a Telegram bot — it cannot be automated without deployed infrastructure but is structurally complete at the code level.

---

_Verified: 2026-03-24T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
