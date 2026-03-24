---
phase: 04-ocr-service
verified: 2026-03-24T00:00:00Z
status: human_needed
score: 7/7 must-haves verified
human_verification:
  - test: "Upload two real Russian passport images via Telegram and trigger OCR. Confirm both photos are accepted and processed."
    expected: "Bot receives both images, calls extract_passport_fields, and returns format_ocr_summary output in the chat."
    why_human: "OCR-01 and OCR-02 (Telegram upload handlers) are Phase 5 concerns. Phase 4 only builds the service layer. The function signature accepts bytes but no Telegram handler exists yet to pass them."
  - test: "Submit a blurry or partially obscured passport image."
    expected: "At least one field in the returned dict is the exact string 'UNCLEAR'. format_ocr_summary shows the warning marker for that field."
    why_human: "Real low-quality image required to verify the UNCLEAR path end-to-end. All automated checks use mocked responses."
  - test: "Trigger a failed OCR call (e.g., invalid API key) and verify error handling."
    expected: "ValueError or anthropic.APIError propagates; bot does not crash silently."
    why_human: "Exception propagation to calling FSM handler is a Phase 5 wiring concern not testable without a live bot."
---

# Phase 4: OCR Service Verification Report

**Phase Goal:** Given two passport image files, the service returns a structured dict of all required passport fields, or flags specific fields as UNCLEAR for human correction.
**Verified:** 2026-03-24
**Status:** human_needed — all automated checks passed; three items require human testing with a live bot (Phase 5 wiring)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                      | Status     | Evidence                                                                                     |
|----|-----------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------|
| 1  | extract_passport_fields(page1_bytes, page2_bytes) accepts raw bytes and returns a 10-field dict            | VERIFIED   | Lines 112-191 in ocr_service.py; signature confirmed; live import test passes               |
| 2  | Any field the model cannot read is returned as exact string 'UNCLEAR' (uppercase)                         | VERIFIED   | _SYSTEM_PROMPT at line 90-96 instructs model; tool schema description at line 63-67          |
| 3  | get_unclear_fields(fields) returns list of field names whose value is 'UNCLEAR'                           | VERIFIED   | Line 200; case-insensitive strip check; 5 unit tests pass covering all edge cases             |
| 4  | format_ocr_summary(fields) returns Telegram-ready Russian string with all 10 fields, UNCLEAR marked       | VERIFIED   | Lines 203-218; all 10 Russian labels confirmed; 4 unit tests pass including marker check     |
| 5  | Images resized to max 1600px via asyncio.to_thread before base64-encoding                                 | VERIFIED   | Lines 131-132: two to_thread calls; _resize_image_bytes uses Pillow thumbnail(1600,1600)     |
| 6  | Claude call uses tool_use with tool_choice forced to extract_passport_fields — not prompt-only JSON       | VERIFIED   | Line 142: tool_choice={"type": "tool", "name": "extract_passport_fields"}                   |
| 7  | Token usage (input_tokens, output_tokens) logged at INFO level after every OCR call                      | VERIFIED   | Lines 180-184: logger.info("OCR complete. input_tokens=%d output_tokens=%d", ...)            |

**Score: 7/7 truths verified**

---

### Required Artifacts

| Artifact                    | Expected                                              | Status     | Details                                                                                              |
|-----------------------------|-------------------------------------------------------|------------|------------------------------------------------------------------------------------------------------|
| `ocr_service.py`            | Complete OCR service module — all public symbols      | VERIFIED   | 219 lines; imports clean; exports PASSPORT_FIELDS (10 items), extract_passport_fields, get_unclear_fields, format_ocr_summary |
| `tests/test_ocr_service.py` | Unit tests for all pure functions + mocked async path | VERIFIED   | 219 lines; 15 tests across 4 classes; all 15 pass; no API key required                               |

---

### Key Link Verification

| From                                         | To                                        | Via                                     | Status     | Details                                                   |
|----------------------------------------------|-------------------------------------------|-----------------------------------------|------------|-----------------------------------------------------------|
| ocr_service.py:extract_passport_fields        | anthropic.AsyncAnthropic.messages.create  | tool_use with _PASSPORT_TOOL schema     | VERIFIED   | Line 137-176; tool_choice name matches _PASSPORT_TOOL name |
| ocr_service.py:_resize_image_bytes            | asyncio.to_thread                         | caller wraps sync Pillow call           | VERIFIED   | Lines 131-132: two explicit to_thread(_resize_image_bytes) calls |
| tests/test_ocr_service.py                    | ocr_service.get_unclear_fields            | direct call with fixture dicts          | VERIFIED   | 5 test functions in TestGetUnclearFields call get_unclear_fields directly |
| tests/test_ocr_service.py                    | ocr_service.extract_passport_fields       | unittest.mock.patch on _CLIENT          | VERIFIED   | 3 async tests in TestExtractPassportFields; AsyncMock used; _CLIENT patched |

---

### Data-Flow Trace (Level 4)

Not applicable. ocr_service.py is a pure service module — it does not render UI or read from a database. It produces a dict that is consumed by the caller. The caller (Phase 5 FSM) is not yet built. format_ocr_summary is a pure function that transforms the dict into a string — no external data source.

---

### Behavioral Spot-Checks

| Behavior                                                     | Command                                                                                                        | Result        | Status  |
|--------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|---------------|---------|
| Module imports without errors                                | python -c "import ocr_service; print('ok')"                                                                   | ok            | PASS    |
| All 4 public symbols present                                 | python -c "import ocr_service; assert all(hasattr(ocr_service, x) for x in ['extract_passport_fields','get_unclear_fields','format_ocr_summary','PASSPORT_FIELDS'])" | exit 0 | PASS |
| PASSPORT_FIELDS has exactly 10 elements                      | python -c "import ocr_service; assert len(ocr_service.PASSPORT_FIELDS)==10"                                   | exit 0        | PASS    |
| get_unclear_fields returns correct subset                    | python -c "from ocr_service import get_unclear_fields, PASSPORT_FIELDS; f={k:'OK' for k in PASSPORT_FIELDS}; f['tenant_full_name']='UNCLEAR'; assert get_unclear_fields(f)==['tenant_full_name']" | exit 0 | PASS |
| 15 tests pass without API key                                | python -m pytest tests/test_ocr_service.py -q                                                                 | 15 passed     | PASS    |
| No regressions in full test suite                            | python -m pytest tests/ -x -q                                                                                  | 57 passed, 1 skipped | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                    | Status          | Evidence                                                                                                                                                                    |
|-------------|-------------|------------------------------------------------------------------------------------------------|-----------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| OCR-01      | 04-01-PLAN  | User can upload photo of first passport page (main data)                                       | PARTIAL         | Service accepts page1_bytes as first arg (function signature is correct). Telegram upload handler does not exist yet — that is Phase 5. Service-layer contract is satisfied. |
| OCR-02      | 04-01-PLAN  | User can upload photo of registration page (propiski page)                                     | PARTIAL         | Service accepts page2_bytes as second arg. Same caveat: Telegram handler is Phase 5. Service-layer contract is satisfied.                                                   |
| OCR-03      | 04-01-PLAN / 04-02-PLAN | System recognizes passport data via Claude Vision API (all 10 fields)              | VERIFIED        | extract_passport_fields calls Claude with tool_use forcing all 10 fields; UNCLEAR used for illegible fields; tested via AsyncMock                                            |
| OCR-04      | 04-01-PLAN / 04-02-PLAN | System shows recognized data for review before contract generation                 | PARTIAL         | format_ocr_summary produces the Russian-language summary with all 10 labels and UNCLEAR markers. Displaying it to the user requires Phase 5 FSM wiring.                     |
| OCR-05      | 04-02-PLAN  | User can confirm or reject recognized data                                                     | NOT_YET_WIRED   | No inline keyboard or confirm/reject handler exists in this phase. This is a Phase 5 FSM concern. The service provides get_unclear_fields to support that flow.              |

**Notes on OCR-01, OCR-02, OCR-04, OCR-05:**

The REQUIREMENTS.md traceability table marks all five OCR requirements as "Phase 4 / Complete". The research file (04-RESEARCH.md) explicitly states OCR-01 and OCR-02 require "Telegram document handler + bot.get_file() download pattern" and OCR-04/05 require "FSM transitions to CONFIRM state" and "Inline keyboard with Confirm / Re-upload buttons". These are Phase 5 deliverables. Phase 4's goal is the standalone service layer. The REQUIREMENTS.md traceability mapping is premature for OCR-01, OCR-02, OCR-04, and OCR-05 — they are partially satisfied by the service API contract but not by end-to-end user-facing behavior. This is an expected split across phases, not a defect in Phase 4.

---

### Anti-Patterns Found

| File                          | Line | Pattern    | Severity | Impact |
|-------------------------------|------|------------|----------|--------|
| No anti-patterns found        | —    | —          | —        | —      |

Scan checked: TODO, FIXME, PLACEHOLDER, return null/[], empty implementations, hardcoded empty data. Zero hits in both `ocr_service.py` and `tests/test_ocr_service.py`.

---

### Human Verification Required

**1. Telegram upload handler integration (OCR-01, OCR-02)**

**Test:** In a live bot session, send two passport photos (or documents). Observe whether the bot downloads them and passes bytes to extract_passport_fields.
**Expected:** Both images are downloaded, passed to the OCR service, and a structured dict is returned.
**Why human:** No Telegram handler exists yet. This is Phase 5 work. Cannot be verified programmatically without a running bot and real Telegram interaction.

**2. UNCLEAR field path with a real low-quality image**

**Test:** Use a blurry, rotated, or partially obscured passport image as input to a live OCR call.
**Expected:** At least one field returns the exact string "UNCLEAR". format_ocr_summary output shows the warning marker for that field.
**Why human:** All tests use a mocked AsyncAnthropic client. The real UNCLEAR path requires an actual Claude API call with a genuinely unclear image.

**3. ValueError propagation to the caller**

**Test:** Pass an invalid API key or simulate a Claude response with no tool_use block. Observe whether the exception propagates cleanly to the eventual FSM caller.
**Expected:** ValueError with message "Claude did not return tool_use block. stop_reason=..." propagates without swallowing.
**Why human:** Phase 5 wiring does not exist yet. Exception handling in the FSM handler cannot be tested in isolation.

---

### Gaps Summary

No blocking gaps. All 7 must-have truths are verified. The 15-test suite passes cleanly. The module is substantive (219 lines), correctly wired internally, and free of stubs or anti-patterns.

OCR-01, OCR-02, OCR-04, and OCR-05 are partially satisfied at the service-contract level but require Phase 5 (FSM dialog layer) to be fully demonstrated to the user. This is by design — Phase 4's goal is "the service returns a structured dict", which is achieved. The Telegram interaction loop (upload, confirm, reject) is Phase 5 scope.

Status is `human_needed` rather than `passed` only because three behaviors cannot be verified without a live bot and real API calls.

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
