---
phase: 06-integration-and-error-handling
plan: 01
subsystem: integration
tags: [python-telegram-bot, sqlalchemy, document-generation, pdf, database]

# Dependency graph
requires:
  - phase: 05-fsm-dialog-layer
    provides: handle_confirm callback, ContractData assembled in FSM state, ConversationHandler
  - phase: 03-document-generation
    provides: generate_contract() async function returning PDF path string
  - phase: 02-validation-and-data-layer
    provides: database.init() and database.save_contract() async functions, ContractData model

provides:
  - Full generate→save→send pipeline wired into handle_confirm
  - database.init() called at bot startup via post_init hook
  - PDF delivered as Telegram document after user confirmation
  - Contract record persisted to SQLite with pdf_path set before save

affects:
  - 06-02-error-handling (errors in generate/save/send now need catching)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ApplicationBuilder.post_init() hook for async database initialization at startup
    - PDF sent via context.bot.send_document() with filesystem-safe filename (replace '/' with '_')
    - context.user_data.clear() after successful pipeline to avoid PicklePersistence bloat
    - contract_data.pdf_path set before save_contract() so DB record has path

key-files:
  created: []
  modified:
    - main.py
    - bot/handlers/conversation.py

key-decisions:
  - "Used ApplicationBuilder.post_init() hook for database.init() — correct async startup pattern inside python-telegram-bot event loop, avoids asyncio.run() collision"
  - "contract_data.pdf_path set before save_contract() call — DB record always reflects actual PDF path, not null"
  - "context.user_data.clear() at end of confirm path — prevents PicklePersistence bloat from storing large ContractData objects across restarts"
  - "Telegram document filename uses contract_number.replace('/', '_') — Telegram rejects filenames with slashes"

patterns-established:
  - "post_init hook pattern: async _post_init(application) -> None calls await database.init()"
  - "Full pipeline order: generate → set pdf_path → save → send → clear user_data"

requirements-completed: [DOC-04]

# Metrics
duration: 1min
completed: 2026-03-24
---

# Phase 6 Plan 1: Integration Pipeline Summary

**PDF contract generation pipeline fully wired: handle_confirm now calls generate_contract(), saves to SQLite with pdf_path, and delivers the PDF as a Telegram document**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-24T08:53:38Z
- **Completed:** 2026-03-24T08:54:47Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Wired `database.init()` into `main.py` startup via `ApplicationBuilder.post_init()` hook — contracts table now exists before any save
- Replaced the stub `handle_confirm` tail with the full generate→save→send pipeline
- After confirmation, bot generates PDF via `generate_contract()`, sets `pdf_path` on `ContractData`, saves to DB via `save_contract()`, and delivers PDF as Telegram document
- `context.user_data.clear()` frees memory and prevents PicklePersistence bloat after successful delivery

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire database.init() into main.py startup** - `cf74273` (feat)
2. **Task 2: Replace handle_confirm stub with full generate→save→send pipeline** - `ee7ac72` (feat)

## Files Created/Modified

- `main.py` - Added `import database`, `_post_init` async function, `.post_init(_post_init)` in ApplicationBuilder chain
- `bot/handlers/conversation.py` - Added `import database` and `generate_contract` import; replaced stub tail of `handle_confirm` with full pipeline

## Decisions Made

- Used `ApplicationBuilder.post_init()` hook for `database.init()` — correct async startup pattern that runs inside the existing event loop, not `asyncio.run()` which would collide
- Set `contract_data.pdf_path` before `save_contract()` so the DB record always has the actual PDF path rather than null
- Used `context.user_data.clear()` at the end of the confirm path to free memory and prevent PicklePersistence from persisting large ContractData objects
- Telegram document filename uses `contract_number.replace('/', '_')` since Telegram rejects filenames with slashes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Core integration pipeline complete — bot can now complete the full contract creation cycle end-to-end
- Ready for Plan 06-02: error handling around generate/save/send pipeline (FileNotFoundError, RuntimeError, IntegrityError, TimeoutExpired)
- No blockers

---
*Phase: 06-integration-and-error-handling*
*Completed: 2026-03-24*

## Self-Check: PASSED

- main.py: FOUND
- bot/handlers/conversation.py: FOUND
- 06-01-SUMMARY.md: FOUND
- commit cf74273: FOUND
- commit ee7ac72: FOUND
