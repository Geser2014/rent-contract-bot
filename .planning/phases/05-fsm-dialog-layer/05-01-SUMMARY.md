---
phase: 05-fsm-dialog-layer
plan: 01
subsystem: dialog
tags: [python-telegram-bot, ConversationHandler, FSM, PicklePersistence, inline-keyboard, ocr]

# Dependency graph
requires:
  - phase: 02-validation-and-data-layer
    provides: validate_date, validate_phone, validate_email, validate_amount, validate_age functions
  - phase: 03-document-generation
    provides: generate_contract_number, ContractData dataclass
  - phase: 04-ocr-service
    provides: extract_passport_fields, get_unclear_fields, format_ocr_summary
provides:
  - bot/handlers/conversation.py with build_conversation_handler() factory
  - All 12 FSM states for contract creation dialog
  - APARTMENTS dict defining Г39 (7 apartments) and Г38 (8 apartments)
  - Inline keyboard handling for group, apartment, deposit method, and confirm
  - Passport upload with photo-type warning handlers
  - ContractData assembly and storage in user_data on confirmation
affects: [06-integration, main.py wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FSM state handlers are thin wiring functions — no business logic, just call service functions"
    - "Error detection via isinstance(result, str) before advancing state"
    - "Always context.user_data.clear() (never = {}) to preserve PicklePersistence reference"
    - "Always await query.answer() as first line of every CallbackQueryHandler callback"
    - "Always query.edit_message_text() after CallbackQuery (never update.message.reply_text)"
    - "Pop large bytes (passport images) from user_data immediately after use"
    - "filters.TEXT & ~filters.COMMAND on all text-input MessageHandlers"

key-files:
  created:
    - bot/__init__.py
    - bot/handlers/__init__.py
    - bot/handlers/conversation.py
  modified: []

key-decisions:
  - "build_conversation_handler() factory pattern — keeps ConversationHandler construction testable and separate from handler logic"
  - "handle_unexpected returns None (not ConversationHandler.END) — keeps user in current state without advancing"
  - "Passport bytes popped from user_data after OCR call — prevents PicklePersistence file bloat"
  - "No document generation or DB save in this phase — Phase 5 ends at ContractData assembly in user_data"

patterns-established:
  - "FSM handler pattern: result = validator(input); if isinstance(result, str): reply + return SAME_STATE"
  - "Apartment keyboard: rows of 4 buttons max using list comprehension with slice"
  - "Deposit method keyboard built inline with half-deposit amount computed from user_data"

requirements-completed: [DIAL-01, DIAL-02, DIAL-03, DIAL-04, DIAL-05, DIAL-06, DIAL-07, DIAL-08, DIAL-09, INFR-03]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 05 Plan 01: FSM Dialog Layer Summary

**ConversationHandler with 12 states wiring all contract dialog steps from /start through OCR confirmation, using PicklePersistence and inline keyboards throughout**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T08:25:46Z
- **Completed:** 2026-03-24T08:27:40Z
- **Tasks:** 1 of 1
- **Files modified:** 3

## Accomplishments
- Created `bot/handlers/conversation.py` with all 12 FSM states and `build_conversation_handler()` factory
- Implemented group/apartment inline keyboard selection with dynamic button layout
- Wired all text-input validators with isinstance error detection and stay-in-state on failure
- Implemented passport page upload handlers with photo-type warnings and OCR integration
- Assembled ContractData from user_data + OCR fields in handle_confirm with age validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create package markers and conversation module skeleton** - `8b20d4f` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `bot/__init__.py` - Package marker for bot/ directory
- `bot/handlers/__init__.py` - Package marker for bot/handlers/ directory
- `bot/handlers/conversation.py` - All 12 FSM state handlers and build_conversation_handler() factory; 420 lines

## Decisions Made
- `build_conversation_handler()` factory pattern separates construction from logic, keeping handlers testable
- `handle_unexpected` returns `None` (not `ConversationHandler.END`) to stay in current state without ending the conversation
- Passport image bytes popped from user_data immediately after OCR to prevent PicklePersistence file bloat
- Phase 5 ends at ContractData assembly in user_data — generate_contract() and database calls are Phase 6 work

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- PTBUserWarning on `build_conversation_handler()`: "If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message." This is a documentation-level advisory from python-telegram-bot, not an error. The per_message=False default is correct for this use case (per-user conversation, not per-message tracking). No action needed.

## Known Stubs

None — all dialog states are fully implemented. ContractData is assembled in user_data. Phase 6 will pick it up from `context.user_data["contract_data"]` to run generate_contract() and database.save_contract().

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FSM dialog layer complete; ready for Phase 6 integration (document generation + DB save)
- `context.user_data["contract_data"]` contains assembled ContractData after CONFIRM state
- main.py still has a stub for bot application setup — Phase 6 will wire build_conversation_handler() into ApplicationBuilder with PicklePersistence

---
*Phase: 05-fsm-dialog-layer*
*Completed: 2026-03-24*
