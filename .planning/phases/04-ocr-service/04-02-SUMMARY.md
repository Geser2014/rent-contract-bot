---
phase: 04-ocr-service
plan: "02"
subsystem: ocr
tags: [ocr, testing, pytest, unittest-mock, pillow, async]
dependency_graph:
  requires:
    - ocr_service.py (04-01 output)
    - Pillow (image creation for synthetic test JPEGs)
    - pytest-asyncio (asyncio_mode=auto in pyproject.toml)
  provides:
    - tests/test_ocr_service.py (15 unit tests, no API calls)
  affects:
    - CI confidence before Phase 05 wires ocr_service into FSM handlers
tech_stack:
  added: []
  patterns:
    - unittest.mock.patch on module-level _CLIENT singleton for async mock
    - asyncio_mode=auto (no @pytest.mark.asyncio decorators needed)
    - Pillow Image.new for synthetic test images (no file fixtures needed)
key_files:
  created:
    - tests/test_ocr_service.py
  modified: []
decisions:
  - omitted @pytest.mark.asyncio decorators — pyproject.toml already has asyncio_mode=auto
  - used module-level helper functions (make_all_clear_fields, make_test_jpeg, _make_mock_response) rather than pytest fixtures — consistent with existing test_document_service.py style
metrics:
  duration_minutes: 5
  completed_date: "2026-03-24"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_satisfied:
  - OCR-03
  - OCR-04
  - OCR-05
---

# Phase 04 Plan 02: OCR Service Tests Summary

**One-liner:** 15-test suite for ocr_service.py covering UNCLEAR detection, Russian label formatting, Pillow resize, and async Claude Vision path via mocked _CLIENT singleton.

## Tasks Completed

| Task | Name                              | Commit  | Files Created          |
|------|-----------------------------------|---------|------------------------|
| 1    | Write unit tests for ocr_service  | 411cdf1 | tests/test_ocr_service.py |

## What Was Built

`tests/test_ocr_service.py` — 15 unit tests across 4 classes:

1. **TestGetUnclearFields (5 tests)**
   - All 10 fields UNCLEAR → returns full PASSPORT_FIELDS list
   - No UNCLEAR values → returns []
   - Mixed → returns only UNCLEAR field names in PASSPORT_FIELDS order
   - Case-insensitive: "unclear" (lowercase) treated as UNCLEAR
   - Whitespace-stripped: "  UNCLEAR  " treated as UNCLEAR

2. **TestFormatOcrSummary (4 tests)**
   - All 10 Russian labels present (ФИО, Дата рождения, Место рождения, Пол, Серия, Номер, Дата выдачи, Кем выдан, Код подразделения, Адрес регистрации)
   - UNCLEAR field values suffixed with " ⚠️ UNCLEAR"
   - Clear fields have no warning marker
   - Header "Данные паспорта" present in output

3. **TestResizeImageBytes (3 tests)**
   - 3200x2400 → longest edge <= 1600 after _resize_image_bytes
   - 800x600 → no upscaling; longest edge stays <= 800
   - Output is valid JPEG bytes (Image.format == "JPEG")

4. **TestExtractPassportFields (3 tests)**
   - Mocked _CLIENT returns correct 10-field dict unchanged
   - ValueError raised when response has no tool_use block (empty content=[])
   - messages.create called exactly once per invocation

## Verification Results

All acceptance criteria passed:

- `tests/test_ocr_service.py` exists with 15 test functions
- `python -m pytest tests/test_ocr_service.py -x -q` → 15 passed
- `python -m pytest tests/ -x -q` → 57 passed, 1 skipped (no regressions)
- AsyncMock used for async path (not skipped)
- No ANTHROPIC_API_KEY or AsyncAnthropic() instantiation in test file
- No @pytest.mark.skip or skipif on core logic tests
- All 4 test classes present

## Deviations from Plan

**1. [Rule — Omitted @pytest.mark.asyncio] asyncio_mode=auto already configured**
- **Found during:** Task 1, pre-flight check of pyproject.toml
- **Action:** Plan noted to check pyproject.toml before adding markers. `asyncio_mode = "auto"` confirmed present. Decorators omitted as instructed.
- **Files modified:** None (decision not to add markers)

## Known Stubs

None — test file contains no hardcoded stubs or placeholder values.

## Self-Check: PASSED

- FOUND: tests/test_ocr_service.py
- FOUND: .planning/phases/04-ocr-service/04-02-SUMMARY.md
- FOUND: commit 411cdf1
