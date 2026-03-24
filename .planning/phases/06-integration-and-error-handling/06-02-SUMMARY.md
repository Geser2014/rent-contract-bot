---
phase: 06-integration-and-error-handling
plan: 02
subsystem: error-handling
tags: [python-telegram-bot, error-boundaries, anthropic, sqlalchemy, subprocess, testing]

# Dependency graph
requires:
  - phase: 06-integration-and-error-handling
    plan: 01
    provides: full generate->save->send pipeline wired into handle_confirm

provides:
  - try/except blocks around OCR call (anthropic.APIError, ValueError) in handle_passport_page2
  - try/except blocks around generate_contract (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError) in handle_confirm
  - try/except block around save_contract (IntegrityError) in handle_confirm
  - tests/test_integration.py with 6 passing error boundary tests

affects:
  - INFR-05 fully satisfied: all three critical operation types (OCR, PDF, DB) have error boundaries

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Error boundary pattern: try/except wrapping external service calls, logger.error(), Russian user message, return safe state
    - OCR failure returns PASSPORT_PAGE1 so user can retry with better image
    - PDF/DB failures return ConversationHandler.END and clear user_data to prevent stale state
    - DB IntegrityError uses context.bot.send_message (not edit_message_text) to avoid message edit conflicts

key-files:
  created:
    - tests/test_integration.py
  modified:
    - bot/handlers/conversation.py

key-decisions:
  - "OCR error returns PASSPORT_PAGE1 (not END) — user can retry with a clearer photo without restarting the whole conversation"
  - "DB IntegrityError uses send_message not edit_message_text — message may already be edited by the generate step, so edit would fail"
  - "context.user_data.clear() on all error paths that return END — prevents stale partial state from polluting next /start"
  - "generate_contract exceptions split into two handlers — TimeoutExpired gets a more specific message than generic RuntimeError/FileNotFoundError"

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 6 Plan 2: Error Boundaries Summary

**Three try/except error boundaries added to conversation.py for OCR, PDF generation, and DB writes — all failures surface user-readable Russian messages instead of unhandled exceptions**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T08:56:56Z
- **Completed:** 2026-03-24T08:58:30Z
- **Tasks:** 2
- **Files modified:** 2 (conversation.py modified, test_integration.py created)

## Accomplishments

- Added `import anthropic`, `import subprocess`, `from sqlalchemy.exc import IntegrityError` to conversation.py
- Wrapped `ocr_service.extract_passport_fields` in `except (anthropic.APIError, ValueError)` — returns PASSPORT_PAGE1 with Russian OCR error message
- Wrapped `generate_contract` in two handlers: `except subprocess.TimeoutExpired` (timeout message) and `except (FileNotFoundError, RuntimeError)` (generic failure message)
- Wrapped `database.save_contract` in `except IntegrityError` — sends Russian duplicate contract message via `send_message` and returns END
- All three error handlers call `logger.error()` before sending user message
- Created `tests/test_integration.py` with 6 tests covering all error paths plus a happy-path smoke test
- Full test suite: 76 passed, 1 skipped (LibreOffice integration test — expected on dev without LibreOffice)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add error boundaries to handle_passport_page2 and handle_confirm** - `fe5acac` (feat)
2. **Task 2: Write error boundary unit tests** - `4509d00` (feat)

## Files Created/Modified

- `bot/handlers/conversation.py` - Added 3 new imports + 3 try/except error boundary blocks (44 lines inserted)
- `tests/test_integration.py` - New file with 6 async test functions, 2 helper builders for document updates and 2 for confirm updates

## Decisions Made

- OCR error returns PASSPORT_PAGE1 so user can retry with a clearer passport photo without restarting the entire conversation
- DB IntegrityError uses `context.bot.send_message` (not `query.edit_message_text`) because the message may already have been edited by the "Генерирую договор..." step — trying to edit it again could fail
- All error paths that return `ConversationHandler.END` call `context.user_data.clear()` to prevent stale partial state from carrying over to the next `/start`
- `generate_contract` exceptions split into two `except` clauses — `TimeoutExpired` gets a distinct "too slow" message vs. generic failure for `FileNotFoundError`/`RuntimeError`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- INFR-05 fully satisfied: OCR, PDF, and DB operations all have error boundaries
- Phase 6 is complete — all 2 plans executed
- Bot now handles all three critical failure modes gracefully without crashing or leaving users with dead conversations

## Known Stubs

None

---
*Phase: 06-integration-and-error-handling*
*Completed: 2026-03-24*
