---
phase: 03-document-generation
plan: 01
subsystem: document-generation
tags: [docxtpl, python-docx, jinja2, docx-templates, contract-generation]

# Dependency graph
requires:
  - phase: 02-validation-and-data-layer
    provides: ContractData dataclass and models.py interface used as input to document_service

provides:
  - document_service.py with generate_contract_number(), _build_context(), _fill_template(), _convert_to_pdf(), generate_contract()
  - storage/templates/Г39/contract_template.docx production Jinja2 template
  - storage/templates/Г38/contract_template.docx production Jinja2 template
  - tests/fixtures/contract_template_test.docx minimal test fixture for unit tests
  - 5 passing unit tests covering DOC-01 and DOC-02

affects: [04-ocr, 05-fsm-dialog, 06-integration]

# Tech tracking
tech-stack:
  added: [docxtpl==0.20.2, python-docx==1.2.0, jinja2==3.1.6, lxml==6.0.2]
  patterns:
    - "_fill_template() is synchronous; called via asyncio.to_thread() in generate_contract()"
    - "All dates pre-formatted as DD.MM.YYYY strings in _build_context() — no Jinja2 strftime filter needed"
    - "Decimal amounts converted to int in _build_context() to avoid .00 suffix in rendered documents"
    - "{%p if condition %} and {%p endif %} each in isolated paragraphs for conditional DOCX sections"
    - "Test fixture at tests/fixtures/contract_template_test.docx covers all context dict keys — avoids dependency on production templates"

key-files:
  created:
    - document_service.py
    - tests/test_document_service.py
    - storage/templates/Г39/contract_template.docx
    - storage/templates/Г38/contract_template.docx
    - tests/fixtures/contract_template_test.docx
    - scripts/create_templates.py
  modified:
    - .gitignore

key-decisions:
  - "docxtpl used for DOCX fill — solves XML run-splitting that defeats raw python-docx"
  - "Same-day contract number collision detection deferred to Phase 6 when DB lookup is wired in; UNIQUE constraint surfaces duplicates at save time"
  - "One template per group (not per apartment) — lookup path is config.TEMPLATES_DIR / group / contract_template.docx"
  - "Test fixture isolated from production templates — tests never depend on Г39/Г38 templates being present"
  - "Added !tests/fixtures/*.docx to .gitignore so test fixture is tracked in git (*.docx was globally ignored)"

patterns-established:
  - "Pattern: document_service functions raise exceptions; FSM layer (Phase 5) will catch and convert to user-facing strings"
  - "Pattern: generate_contract() cleans up temp DOCX in finally block — cleanup on success AND failure"

requirements-completed: [DOC-01, DOC-02]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 3 Plan 1: Document Templates and Service (DOC-01/DOC-02) Summary

**docxtpl-based DOCX contract fill pipeline with Jinja2 templates for Г39/Г38, deposit split/lump-sum conditionals, and 5 passing unit tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T07:32:38Z
- **Completed:** 2026-03-24T07:35:22Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Production DOCX templates created for both apartment groups (Г39 and Г38) with full Jinja2 {{ }} placeholder syntax and {%p if deposit_split %} conditional blocks
- document_service.py implemented with generate_contract_number() (DOC-01), _build_context(), _fill_template(), _convert_to_pdf(), and generate_contract() async entry point (DOC-02)
- 5 unit tests written and passing via TDD (RED then GREEN) — contract number format, all-placeholder replacement, deposit_split=True, deposit_split=False
- Full test suite grew from 35 to 40 tests, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create DOCX contract templates with Jinja2 placeholders** - `0efa90c` (feat)
2. **Task 2: Implement document_service.py with TDD** - `1f31509` (feat)

**Plan metadata:** committed with final docs commit

_Note: TDD task included RED (failing import error) and GREEN (5 tests pass) phases in a single commit._

## Files Created/Modified

- `document_service.py` - Contract number generation, context building, template fill, LibreOffice conversion, async generate_contract()
- `tests/test_document_service.py` - 5 unit tests: TestContractNumber (2) + TestFillTemplate (3)
- `storage/templates/Г39/contract_template.docx` - Production Jinja2 template for group Г39
- `storage/templates/Г38/contract_template.docx` - Production Jinja2 template for group Г38
- `tests/fixtures/contract_template_test.docx` - Minimal test fixture covering all context dict keys
- `scripts/create_templates.py` - One-time script used to generate the DOCX files programmatically
- `.gitignore` - Added `!tests/fixtures/*.docx` exception so fixture is tracked

## Decisions Made

- Used docxtpl for template rendering (not raw python-docx) — solves XML run-splitting problem
- Same-day collision detection deferred to Phase 6; UNIQUE constraint on contract_number handles duplicates at DB save
- One template per group, not per apartment — aligns with config.py TEMPLATES_DIR / group path structure
- Test fixture isolated so unit tests never need production templates present
- .gitignore exception added for tests/fixtures/*.docx (Rule 2 deviation — tests would break without it)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added .gitignore exception for tests/fixtures/*.docx**
- **Found during:** Task 1 (template creation)
- **Issue:** .gitignore had `*.docx` globally — test fixture at tests/fixtures/contract_template_test.docx would be untracked, causing tests to fail after clone
- **Fix:** Added `!tests/fixtures/*.docx` exception to .gitignore so the fixture is committed and available in all environments
- **Files modified:** .gitignore
- **Verification:** git status showed tests/fixtures/ as tracked after the change
- **Committed in:** 0efa90c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Fix essential — without it, tests would fail after a fresh clone of the repo. No scope creep.

## Issues Encountered

- docxtpl was not installed in the dev environment. Installed via `pip install docxtpl==0.20.2` before task execution (expected per research notes).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- document_service.py is complete and tested for DOCX fill (DOC-01 + DOC-02)
- LibreOffice PDF conversion (DOC-03) is implemented in _convert_to_pdf() but requires LibreOffice on server — integration tests are in Plan 02
- Phase 4 (OCR) can import and call generate_contract() once passport data is available
- Phase 5 (FSM) will call generate_contract() with fully-populated ContractData

## Self-Check: PASSED

- FOUND: document_service.py
- FOUND: tests/test_document_service.py
- FOUND: storage/templates/Г39/contract_template.docx
- FOUND: storage/templates/Г38/contract_template.docx
- FOUND: tests/fixtures/contract_template_test.docx
- FOUND: .planning/phases/03-document-generation/03-01-SUMMARY.md
- FOUND: commit 0efa90c (Task 1)
- FOUND: commit 1f31509 (Task 2)

---
*Phase: 03-document-generation*
*Completed: 2026-03-24*
