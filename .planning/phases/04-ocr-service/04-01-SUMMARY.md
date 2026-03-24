---
phase: 04-ocr-service
plan: "01"
subsystem: ocr
tags: [ocr, anthropic, claude-vision, passport, async, pillow]
dependency_graph:
  requires:
    - config.py (ANTHROPIC_KEY)
    - Pillow (image resize)
    - anthropic SDK 0.86.0
  provides:
    - ocr_service.py (extract_passport_fields, get_unclear_fields, format_ocr_summary, PASSPORT_FIELDS)
  affects:
    - Phase 05 FSM dialog layer (calls extract_passport_fields from PASSPORT states)
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread wrapping synchronous Pillow resize
    - tool_use with forced tool_choice for deterministic Claude JSON output
    - Module-level AsyncAnthropic singleton (not recreated per call)
key_files:
  created:
    - ocr_service.py
  modified: []
decisions:
  - Used module-level _CLIENT singleton (not per-call) per plan specification — avoids unnecessary object creation on every OCR call
  - format_ocr_summary uses " ⚠️ UNCLEAR" suffix (not "!" as in research) — matches plan action spec exactly
  - PASSPORT_FIELDS ordered to match ContractData field declaration order in models.py
metrics:
  duration_minutes: 2
  completed_date: "2026-03-24"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_satisfied:
  - OCR-01
  - OCR-02
  - OCR-03
  - OCR-04
  - OCR-05
---

# Phase 04 Plan 01: OCR Service Summary

**One-liner:** Async passport OCR module using Claude Vision tool_use with forced schema, Pillow resize, and UNCLEAR field flagging for deterministic structured output.

## Tasks Completed

| Task | Name                          | Commit  | Files Created      |
|------|-------------------------------|---------|-------------------|
| 1    | Implement ocr_service.py      | ef1687a | ocr_service.py    |

## What Was Built

`ocr_service.py` at project root — a Telegram-agnostic async service that:

1. **`extract_passport_fields(page1_bytes, page2_bytes) -> dict[str, str]`**
   - Resizes both passport images to max 1600px via `asyncio.to_thread(_resize_image_bytes)` — prevents blocking the event loop and reduces token cost
   - Base64-encodes the resized JPEG bytes
   - Calls `_CLIENT.messages.create()` with `tool_choice={"type": "tool", "name": "extract_passport_fields"}` — forces deterministic tool_use output, never prose JSON
   - Logs `input_tokens` and `output_tokens` at INFO level after every successful call
   - Raises `ValueError` if Claude returns no `tool_use` block (guarded against edge cases)

2. **`_resize_image_bytes(raw_bytes, max_px=1600) -> bytes`**
   - Synchronous helper; Pillow `thumbnail()` with LANCZOS for quality, saves as JPEG quality=92
   - No-op if image is already within bounds

3. **`get_unclear_fields(fields) -> list[str]`**
   - Returns field names from `PASSPORT_FIELDS` where value is `"UNCLEAR"` (case-insensitive, strip-trimmed)

4. **`format_ocr_summary(fields) -> str`**
   - Returns multi-line Russian Telegram message; UNCLEAR values marked with `⚠️ UNCLEAR` suffix

5. **`PASSPORT_FIELDS`** — ordered list of 10 field names matching `ContractData` passport fields exactly

## Verification Results

All acceptance criteria passed:

- `python -c "import ocr_service"` exits 0
- All 4 public symbols exportable
- `AsyncAnthropic` used (not sync), module-level singleton
- `asyncio.to_thread` appears on 2 actual call lines (lines 131 and 132)
- `tool_choice` contains `"extract_passport_fields"`
- `UNCLEAR` appears in system prompt, tool description, `get_unclear_fields`, and `format_ocr_summary`
- `input_tokens` logged at INFO in `extract_passport_fields`
- `raise ValueError` guards missing tool_use block
- `len(PASSPORT_FIELDS) == 10`

```
['tenant_full_name', 'tenant_dob', 'tenant_birthplace', 'tenant_gender', 'passport_series',
 'passport_number', 'passport_issued_date', 'passport_issued_by', 'passport_division_code',
 'tenant_address']

get_unclear_fields({'tenant_full_name': 'UNCLEAR', 'tenant_birthplace': 'UNCLEAR', ...})
=> ['tenant_full_name', 'tenant_birthplace']
```

## Deviations from Plan

None — plan executed exactly as written.

The research file (04-RESEARCH.md) showed `_CLIENT` created per-call inside `extract_passport_fields`, but the plan action spec explicitly required a module-level singleton. The plan took precedence.

## Known Stubs

None — `ocr_service.py` contains no hardcoded stubs or placeholder values. The `UNCLEAR` string is a legitimate sentinel value, not a stub.

## Self-Check: PASSED

- FOUND: ocr_service.py
- FOUND: .planning/phases/04-ocr-service/04-01-SUMMARY.md
- FOUND: commit ef1687a
