---
phase: 02-validation-and-data-layer
plan: 01
subsystem: validation
tags: [validators, datetime, decimal, regex, pure-functions, tdd, pytest]

# Dependency graph
requires:
  - phase: 01-infrastructure
    provides: pyproject.toml with pytest config (asyncio_mode=auto), ruff settings, Python 3.10+ target

provides:
  - Five pure validation functions: validate_date, validate_phone, validate_email, validate_amount, validate_age
  - Result-style return contract: normalized value on success, Russian error string on failure
  - Full pytest unit coverage: 26 tests across all five validators

affects:
  - 02-validation-and-data-layer (plan 02 — data models will import these validators)
  - 03-fsm-conversation-handler (FSM states call validators before storing to user_data)
  - Any module that accepts user input from Telegram dialog

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Result-style return: success returns typed value (datetime.date | str | Decimal | bool), failure returns Russian-language error string — callers use isinstance(result, str) to detect errors"
    - "Pure validators: no I/O, no logging, no side effects — fully unit-testable in isolation"
    - "stdlib only for validators: datetime, re, decimal — no external dependencies"

key-files:
  created:
    - validators.py
    - tests/__init__.py
    - tests/test_validators.py
  modified: []

key-decisions:
  - "Result-style returns (value | str) instead of raising exceptions — callers use isinstance(result, str) for error detection, enabling clean FSM guard logic"
  - "stdlib only (datetime, re, decimal) — no pydantic in validators.py to keep the validation layer dependency-free and importable anywhere"
  - "Phone validation accepts only +7 prefix (Russian numbers only) — intentional per PROJECT.md (Russian-only use case)"
  - "Email validation uses simple regex (not RFC 5322) — intentional, single-user bot does not need strict RFC compliance"

patterns-established:
  - "Validator return contract: SUCCESS = typed value, FAILURE = Russian str — all five validators follow this contract"
  - "TDD cycle: write failing tests first, commit RED state, implement to GREEN, commit GREEN state"

requirements-completed: [VALD-01, VALD-02, VALD-03, VALD-04, VALD-05, VALD-06]

# Metrics
duration: 1min
completed: 2026-03-24
---

# Phase 2 Plan 01: Field Validators Summary

**Five pure Python validators (date, phone, email, amount, age) with Result-style returns and 26 pytest tests passing, using stdlib only**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-24T07:04:10Z
- **Completed:** 2026-03-24T07:05:35Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented `validate_date` using `strptime("%d.%m.%Y")` — accepts leading zeros or single digits, returns `datetime.date` or Russian error
- Implemented `validate_phone` with `+7\d{10}` regex — normalizes spaced input, rejects non-Russian numbers
- Implemented `validate_email` with fullmatch regex — lowercases valid email, rejects malformed input
- Implemented `validate_amount` with `Decimal` parsing — strips spaces, enforces > 0, returns exact `Decimal` (not float)
- Implemented `validate_age` using pure arithmetic age calculation — checks 18+ on contract date, handles DOB > contract date edge case
- 26 pytest tests covering all valid/invalid input cases — all pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for all five validators** - `76bdfed` (test)
2. **Task 2: Implement validators.py to pass all tests** - `a8621a0` (feat)

**Plan metadata:** (pending final commit)

_Note: TDD tasks have two commits — test (RED) then feat (GREEN)_

## Files Created/Modified

- `validators.py` - Five pure validation functions with Result-style returns
- `tests/__init__.py` - Empty package init for test discovery
- `tests/test_validators.py` - 26 pytest tests across all five validators (134 lines)

## Decisions Made

- Result-style returns (value | str) chosen over exceptions — enables clean `isinstance(result, str)` guard in FSM states without try/except blocks
- stdlib only for validators — no pydantic dependency keeps this layer portable and importable without side effects
- Phone validation restricts to Russian +7 numbers — intentional per PROJECT.md (Russian-only use case, single landlord)
- Simple email regex (not RFC 5322) — adequate for single-user bot, avoids false negatives on valid addresses

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- pytest not installed in Python environment (Rule 3 - blocking): installed pytest and pytest-asyncio via pip to run tests. This is a one-time dev environment setup, not a code change.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all validators are fully implemented and return live computed values.

## Next Phase Readiness

- All five validators ready for import by FSM states and data models
- Contract: `from validators import validate_date, validate_phone, validate_email, validate_amount, validate_age`
- Callers use `isinstance(result, str)` to detect validation failure
- Ready for Phase 02 Plan 02 (data models / SQLAlchemy schema)

## Self-Check: PASSED

- validators.py: FOUND
- tests/__init__.py: FOUND
- tests/test_validators.py: FOUND
- 02-01-SUMMARY.md: FOUND
- commit 76bdfed (test RED): FOUND
- commit a8621a0 (feat GREEN): FOUND

---
*Phase: 02-validation-and-data-layer*
*Completed: 2026-03-24*
