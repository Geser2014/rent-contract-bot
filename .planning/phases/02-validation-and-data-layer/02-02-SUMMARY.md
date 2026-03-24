---
phase: 02-validation-and-data-layer
plan: "02"
subsystem: database
tags: [sqlalchemy, aiosqlite, sqlite, orm, dataclass, pytest-asyncio]

# Dependency graph
requires:
  - phase: 01-infrastructure
    provides: config.DB_PATH, logger.get_logger(), pyproject.toml asyncio_mode=auto

provides:
  - ContractData dataclass (DTO used by all layers: FSM, document generation, persistence)
  - Contract SQLAlchemy ORM model with 'contracts' table schema
  - Base DeclarativeBase for ORM models
  - database.init() — async idempotent table creation
  - database.save_contract() — async insert returning row id
  - database._configure() — test injection hook for in-memory DB

affects: [03-document-generation, 05-conversation-fsm, 06-integration]

# Tech tracking
tech-stack:
  added: [SQLAlchemy==2.0.48, aiosqlite==0.22.1, greenlet==3.3.2]
  patterns:
    - SQLAlchemy 2.0 async engine with create_async_engine + AsyncSession
    - Module-level engine with _configure() hook for test isolation (in-memory DB)
    - TDD pattern: failing test first, then implementation
    - Timezone-aware datetime.now(UTC) instead of deprecated utcnow()

key-files:
  created:
    - models.py
    - database.py
    - tests/test_database.py
    - tests/test_models.py
    - tests/__init__.py
  modified: []

key-decisions:
  - "Used _configure() hook in database.py to enable test isolation with in-memory SQLite — avoids touching storage/ in tests"
  - "Fixed deprecated datetime.utcnow() to use timezone-aware datetime.now(datetime.UTC) — Python 3.12 compatibility"
  - "Contract ORM created_at uses lambda default for timezone-aware datetime, explicit value set in save_contract()"

patterns-established:
  - "TDD: write failing tests first, then minimal implementation to pass"
  - "All DB tests use autouse fixture to redirect engine to :memory: — zero side effects"
  - "database.py imports from config at module load; tests call _configure() before init() to override"

requirements-completed: [DB-01, DB-02]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 02 Plan 02: ContractData DTO and Async Database Layer Summary

**ContractData dataclass DTO + Contract SQLAlchemy ORM model + async SQLite layer (init/save) with 9 passing tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T07:04:19Z
- **Completed:** 2026-03-24T07:07:14Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- ContractData dataclass with all 21 contract fields as the shared DTO across all layers
- Contract SQLAlchemy ORM model mapping to 'contracts' table with complete schema (23 columns)
- Async database.py with idempotent init() and save_contract() returning row id
- 4 database tests (init idempotency, round-trip save, field persistence) + 5 model tests — all green
- Auto-installed SQLAlchemy==2.0.48 and aiosqlite==0.22.1 (missing from local Python env)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create models.py with ContractData dataclass and Contract ORM model** - `1184b71` (feat)
2. **Task 2: Create database.py and tests/test_database.py** - `44bb8f9` (feat)

_Note: TDD tasks — failing tests written first, implementation second_

## Files Created/Modified
- `models.py` - ContractData dataclass (DTO) and Contract ORM model with Base
- `database.py` - Async SQLAlchemy engine, _configure(), init(), save_contract()
- `tests/test_database.py` - 4 pytest-asyncio tests for DB layer
- `tests/test_models.py` - 5 tests for ContractData and Contract ORM model
- `tests/__init__.py` - Empty init file for tests package

## Decisions Made
- Used `_configure(url)` hook in database.py so tests can inject in-memory SQLite without patching globals — clean test isolation
- Fixed `datetime.utcnow()` deprecation (Python 3.12 warns) — using `datetime.now(datetime.UTC)` throughout
- Contract ORM `created_at` uses a lambda default (timezone-aware) rather than the deprecated `utcnow` callable

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing SQLAlchemy and aiosqlite packages**
- **Found during:** Task 1 (TDD RED phase)
- **Issue:** `ModuleNotFoundError: No module named 'sqlalchemy'` — packages in requirements.txt but not installed in local Python env
- **Fix:** `pip install SQLAlchemy==2.0.48 aiosqlite==0.22.1` (exact versions from requirements.txt)
- **Files modified:** None (local pip install, not committed)
- **Verification:** All tests pass after install
- **Committed in:** 1184b71 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed deprecated datetime.utcnow() usage**
- **Found during:** Task 2 (TDD GREEN phase — deprecation warning in test output)
- **Issue:** Python 3.12 warns that `datetime.datetime.utcnow()` is deprecated and scheduled for removal
- **Fix:** Replaced with `datetime.datetime.now(datetime.UTC)` in database.py; updated Contract ORM default to timezone-aware lambda
- **Files modified:** database.py, models.py
- **Verification:** Tests pass with 0 warnings
- **Committed in:** 44bb8f9 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correct operation. No scope creep.

## Issues Encountered
None beyond the auto-fixed issues above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ContractData DTO is ready for Phase 3 (document generation) and Phase 5 (FSM)
- database.init() + save_contract() ready for Phase 6 integration wiring
- Full test suite at 35 tests passing (validators + database + models)
- DB schema stable: 23-column 'contracts' table verified via PRAGMA table_info

---
*Phase: 02-validation-and-data-layer*
*Completed: 2026-03-24*
