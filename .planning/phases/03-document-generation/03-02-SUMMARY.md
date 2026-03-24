---
phase: 03-document-generation
plan: 02
subsystem: document-generation
tags: [pytest, subprocess, asyncio, libreoffice, docx-pdf, mocking, tempfile]

# Dependency graph
requires:
  - phase: 03-document-generation-01
    provides: document_service.py with _convert_to_pdf() and generate_contract() already implemented

provides:
  - TestPdfConversion class (3 tests) in tests/test_document_service.py
  - pytest integration mark registered in pyproject.toml
  - DOC-03 behavior verified: RuntimeError on no-PDF output, finally-block cleanup confirmed

affects: [04-ocr, 05-fsm-dialog, 06-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Integration tests tagged @pytest.mark.integration + @pytest.mark.skipif(shutil.which) — skipped automatically in environments without LibreOffice"
    - "Mock subprocess.run with MagicMock to test LibreOffice error guard without requiring LibreOffice"
    - "patch.object on module-level functions (_fill_template, _convert_to_pdf) to isolate generate_contract orchestration logic"
    - "pytest markers registered in pyproject.toml [tool.pytest.ini_options] markers array to suppress PytestUnknownMarkWarning"

key-files:
  created: []
  modified:
    - tests/test_document_service.py
    - pyproject.toml

key-decisions:
  - "TestPdfConversion tests pass immediately (GREEN without RED) because _convert_to_pdf and generate_contract were already complete from Plan 01 — this is the expected TDD outcome for a verification-focused plan"
  - "Registered 'integration' pytest mark in pyproject.toml to eliminate PytestUnknownMarkWarning (Rule 2 — warning would appear in all future test runs)"

patterns-established:
  - "Pattern: use patch.object(document_service, '_convert_to_pdf', side_effect=RuntimeError) to test finally-block cleanup without requiring LibreOffice"
  - "Pattern: Integration tests that require system tools use @pytest.mark.skipif(shutil.which('tool') is None) — zero test failures on dev machines without the tool"

requirements-completed: [DOC-03]

# Metrics
duration: 8min
completed: 2026-03-24
---

# Phase 3 Plan 2: LibreOffice PDF Conversion Tests (DOC-03) Summary

**TestPdfConversion class with 3 tests verifying RuntimeError on no-output, finally-block temp-file cleanup, and skipped LibreOffice integration test — 42 tests pass (1 skipped)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-24T07:36:40Z
- **Completed:** 2026-03-24T07:44:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- TestPdfConversion class appended to tests/test_document_service.py with all 3 required tests
- test_convert_to_pdf_raises_when_no_output: mocks subprocess.run (exit 0, no PDF created on disk) — asserts RuntimeError("no output") raised by _convert_to_pdf guard
- test_generate_contract_cleanup_on_failure: patches _fill_template to return a real sentinel file, patches _convert_to_pdf to raise — asserts renamed temp DOCX is deleted by finally block
- test_pdf_conversion_integration: marked @pytest.mark.integration + @pytest.mark.skipif(shutil.which("libreoffice") is None) — automatically skipped on Windows dev, will run on Ubuntu server
- Registered 'integration' pytest mark in pyproject.toml — eliminates PytestUnknownMarkWarning in all future test runs
- Full suite: 42 passed, 1 skipped — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add TestPdfConversion tests and verify _convert_to_pdf + generate_contract** - `8000ace` (feat)

**Plan metadata:** committed with final docs commit

## Files Created/Modified

- `tests/test_document_service.py` - TestPdfConversion class appended (3 tests: unit mock + cleanup + integration skip)
- `pyproject.toml` - Added markers registration for 'integration' pytest mark

## Decisions Made

- Tests pass GREEN immediately: _convert_to_pdf and generate_contract were fully implemented in Plan 01. This is the expected outcome — Plan 02 exists to prove the DOC-03 contract via tests, not to add implementation.
- Registered 'integration' mark in pyproject.toml to prevent PytestUnknownMarkWarning from polluting all future test output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Registered 'integration' pytest mark in pyproject.toml**
- **Found during:** Task 1 (running tests after adding TestPdfConversion)
- **Issue:** @pytest.mark.integration was unregistered — caused PytestUnknownMarkWarning on every test run; unregistered marks are silently ignored by pytest's -m filter, making integration test selection unreliable
- **Fix:** Added markers array to [tool.pytest.ini_options] in pyproject.toml with 'integration' mark description
- **Files modified:** pyproject.toml
- **Verification:** Re-ran test suite — PytestUnknownMarkWarning absent; 42 passed, 1 skipped
- **Committed in:** 8000ace (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Fix essential for CI reliability — unregistered marks cause silent failures when filtering with -m. No scope creep.

## Issues Encountered

None — _convert_to_pdf and generate_contract were already correctly implemented in Plan 01. Tests went directly GREEN without requiring any implementation changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 document generation pipeline is fully tested (DOC-01, DOC-02, DOC-03 all covered)
- LibreOffice integration test will run automatically on Ubuntu server where LibreOffice is available
- generate_contract() is the verified public API for Phase 4 (OCR) and Phase 5 (FSM) to call
- Phase 4 (OCR) can import document_service.generate_contract() immediately — no further Phase 3 work needed

## Self-Check: PASSED

- FOUND: tests/test_document_service.py (TestPdfConversion class with 3 tests)
- FOUND: pyproject.toml (markers registration added)
- FOUND: commit 8000ace (Task 1)
- VERIFIED: 42 tests pass, 1 skipped (integration)
- VERIFIED: _convert_to_pdf has --norestore, --nofirststartwizard, resolve(), timeout=30, expected_pdf.exists()
- VERIFIED: generate_contract has asyncio.to_thread, finally block, tmp_docx.unlink()

---
*Phase: 03-document-generation*
*Completed: 2026-03-24*
