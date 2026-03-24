---
phase: 05-fsm-dialog-layer
plan: 02
subsystem: dialog
tags: [python-telegram-bot, ApplicationBuilder, PicklePersistence, ConversationHandler, unit-tests, FSM]

# Dependency graph
requires:
  - phase: 05-fsm-dialog-layer
    plan: 01
    provides: build_conversation_handler(), all 12 FSM state handlers, APARTMENTS dict
  - config.py
    provides: BOT_TOKEN, PERSISTENCE_PATH, LOG_LEVEL, LOGS_DIR
provides:
  - main.py with full ApplicationBuilder + PicklePersistence + ConversationHandler wiring
  - tests/test_conversation.py with 13 unit tests for state transition logic
affects: [06-integration, bot startup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ApplicationBuilder chain: .token().persistence().concurrent_updates(False).build()"
    - "drop_pending_updates=True on run_polling discards stale messages after bot restart"
    - "validate_phone and validate_email return str on both success and error — check via re.fullmatch, not isinstance"
    - "asyncio_mode=auto in pyproject.toml — no @pytest.mark.asyncio decorators needed"

key-files:
  created:
    - tests/test_conversation.py
  modified:
    - main.py
    - bot/handlers/conversation.py

key-decisions:
  - "Use re.fullmatch in handle_phone/handle_email to distinguish valid output from error — isinstance(str) check was always True since both success and error are strings"
  - "PicklePersistence initialized with filepath=str(config.PERSISTENCE_PATH) for FSM state persistence across bot restarts"
  - "concurrent_updates=False required by python-telegram-bot for ConversationHandler to work correctly"

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 05 Plan 02: Bot Wiring and Conversation Tests Summary

**main.py wired with ApplicationBuilder + PicklePersistence + ConversationHandler registration; 13 unit tests added covering all state transitions including /cancel, valid/invalid inputs, and APARTMENTS structure**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T08:29:46Z
- **Completed:** 2026-03-24T08:32:41Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Updated `main.py` with full ApplicationBuilder setup: PicklePersistence, concurrent_updates=False, ConversationHandler registered, run_polling(drop_pending_updates=True)
- Created `tests/test_conversation.py` with 13 tests: /cancel, /start, group selection, date validation, amount validation, phone validation, passport photo warnings, unexpected message, and APARTMENTS structure
- Fixed a pre-existing bug in `handle_phone` and `handle_email`: both validators return `str` for both success and error, making `isinstance(result, str)` always `True` — phone and email handlers never advanced state. Fixed with `re.fullmatch` checks.

## Task Commits

1. **Task 1: Wire main.py with ApplicationBuilder + PicklePersistence** - `f625a8b` (feat)
2. **Task 2: Add conversation unit tests + fix phone/email handler bug** - `e532c55` (feat)

## Files Created/Modified

- `main.py` - Full bot entry point with ApplicationBuilder, PicklePersistence(config.PERSISTENCE_PATH), concurrent_updates=False, ConversationHandler, run_polling(drop_pending_updates=True)
- `tests/test_conversation.py` - 13 unit tests covering all required state transitions, 120 lines
- `bot/handlers/conversation.py` - Added `import re`; fixed `handle_phone` and `handle_email` to use `re.fullmatch` instead of broken `isinstance(result, str)` check

## Decisions Made

- Fixed `handle_phone`/`handle_email` with `re.fullmatch` since `validate_phone`/`validate_email` return `str` for both success and failure — the `isinstance(result, str)` pattern is only correct when success returns a non-string type (like `datetime.date` or `Decimal`)
- `PicklePersistence` initialized with `filepath=str(config.PERSISTENCE_PATH)` ensuring FSM state survives bot restarts
- `concurrent_updates=False` required by python-telegram-bot for ConversationHandler (prevents parallel message processing that would corrupt FSM state)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed phone and email handlers never advancing state**

- **Found during:** Task 2 (test_handle_phone_valid failed — returned PHONE instead of EMAIL)
- **Issue:** `handle_phone` used `isinstance(result, str)` to detect errors, but `validate_phone` returns `str` on both valid output (`"+79991234567"`) and error (Russian error string). Result: valid phones were always treated as errors; the handler would never reach the email step. Same bug in `handle_email`.
- **Fix:** Replaced `isinstance(result, str)` with `re.fullmatch(r'\+7\d{10}', result)` in `handle_phone` and `re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', result)` in `handle_email`. Added `import re` to `bot/handlers/conversation.py`.
- **Files modified:** `bot/handlers/conversation.py`
- **Commit:** `e532c55`

## Known Stubs

None — main.py is fully wired and runnable. Tests cover all state transitions without stubs.

## User Setup Required

None — bot runs with existing `.env` configuration (TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY).

## Next Phase Readiness

- Bot is end-to-end runnable: `python main.py` starts the bot with full FSM dialog
- INFR-02 (/start begins dialog): ConversationHandler entry point registered and verified
- INFR-03 (/cancel cancels at any stage): fallback CommandHandler registered and tested
- Phase 6 will wire `context.user_data["contract_data"]` into generate_contract() and database.save_contract()

---
*Phase: 05-fsm-dialog-layer*
*Completed: 2026-03-24*
