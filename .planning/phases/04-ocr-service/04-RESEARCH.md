# Phase 4: OCR Service — Research

**Researched:** 2026-03-24
**Domain:** Claude Vision API — Russian passport OCR with structured output and UNCLEAR fallback
**Confidence:** HIGH — stack pre-selected, all findings cross-verified against existing project research and official Anthropic SDK patterns

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OCR-01 | User can upload photo of first passport page (main data) | Telegram document handler + `bot.get_file()` download pattern; document-type upload required (not photo) |
| OCR-02 | User can upload photo of registration page | Same download pattern; both images passed in a single Claude API call |
| OCR-03 | System recognizes passport data via Claude Vision API (all 10 fields) | `tool_use` structured output forces exact JSON schema matching ContractData fields; UNCLEAR fallback for ambiguous fields |
| OCR-04 | System shows recognized data for review before contract generation | Format 10 fields as a readable Russian-language summary; FSM transitions to CONFIRM state |
| OCR-05 | User can confirm or reject recognized data | Inline keyboard with "Confirm" / "Re-upload" buttons; rejection loops back to OCR-01 state |
</phase_requirements>

---

## Summary

Phase 4 builds a single Python module, `ocr_service.py`, that accepts two image byte streams (passport main page and registration page), calls the Anthropic Claude Vision API using `tool_use` for deterministic JSON output, and returns either a fully-populated dict of 10 passport fields or raises a typed exception. The module has no Telegram dependency — it is a pure async service consumed by FSM handlers.

The critical design constraint is that Claude Vision can hallucinate on low-quality, blurry, or rotated passport photos. The UNCLEAR fallback strategy (instruct the model to return the literal string `"UNCLEAR"` for any field it cannot read with confidence) is the primary mitigation. The confirmation step (OCR-04/05) is a mandatory second line of defense where the human verifies all extracted fields before contract generation.

The stack is fully pre-selected and already installed (`anthropic==0.86.0`, `Pillow==11.2.1`). Passport images must be received as Telegram documents (not photos) to avoid Telegram's lossy JPEG compression. Images should be resized to max 1600px before base64-encoding to keep API token costs manageable.

**Primary recommendation:** Implement `ocr_service.py` as a thin async wrapper around `AsyncAnthropic.messages.create()` using `tool_use` with a strict JSON schema for the 10 passport fields. Use `asyncio.to_thread()` for the Pillow resize step (sync). Validate returned fields and mark any `"UNCLEAR"` values before passing to the confirmation formatter.

---

## Standard Stack

### Core (already installed — no new installs required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.86.0 | Claude Vision API client | Official SDK; `AsyncAnthropic` is the required async client for use inside python-telegram-bot handlers |
| Pillow | 11.2.1 | Image resize before API call | Already in requirements.txt; `Image.thumbnail()` for max-1600px resize without distortion |
| httpx | 0.28.1 | Download Telegram file bytes | Already used by anthropic SDK internally; async-native HTTP client |
| base64 (stdlib) | — | Encode image bytes for Claude API | No extra dep; `base64.standard_b64encode(bytes).decode()` |
| io (stdlib) | — | BytesIO for Pillow in-memory resize | No extra dep |

### No New Dependencies

All libraries needed for Phase 4 are already present in `requirements.txt`. No `pip install` steps required.

---

## Architecture Patterns

### Recommended File: `ocr_service.py` (top-level, alongside `document_service.py`)

```
rent-contract-bot/
├── ocr_service.py          ← NEW: Claude Vision wrapper (this phase)
├── document_service.py     ← EXISTS: DOCX/PDF generation
├── validators.py           ← EXISTS: field validators
├── models.py               ← EXISTS: ContractData dataclass
├── config.py               ← EXISTS: ANTHROPIC_KEY constant
└── tests/
    └── test_ocr_service.py ← NEW: unit tests for this phase
```

Pattern is consistent with existing top-level service modules (`document_service.py`, `validators.py`).

### Pattern 1: AsyncAnthropic with tool_use for Structured JSON

**What:** Pass both passport images and a `tools` definition to the Claude API. The tool schema enforces the exact JSON shape needed. Claude is forced to emit a JSON object matching the schema — no prose parsing required.

**When to use:** Any time you need deterministic structured output from a Claude call. Mandatory for passport OCR.

**Why tool_use over prompt-only JSON:** Prompting Claude to "respond as JSON" produces JSON most of the time but not always. `tool_use` with an explicit JSON schema is enforced at the API level — the response is always a valid tool call argument block.

**Example (verified against anthropic SDK 0.86.0 patterns and official Anthropic tool_use docs):**

```python
# Source: Anthropic tool_use documentation + official SDK patterns
import asyncio
import base64
import io
import logging
from pathlib import Path

import anthropic
from PIL import Image

import config

logger = logging.getLogger(__name__)

_CLAUDE_MODEL = "claude-sonnet-4-6"

_PASSPORT_TOOL = {
    "name": "extract_passport_fields",
    "description": (
        "Extract all required fields from a Russian internal passport. "
        "Use exactly 'UNCLEAR' (uppercase) for any field that is illegible, "
        "blurry, partially occluded, or ambiguous."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tenant_full_name":        {"type": "string", "description": "ФИО полностью (Фамилия Имя Отчество)"},
            "tenant_dob":              {"type": "string", "description": "Дата рождения в формате ДД.ММ.ГГГГ"},
            "tenant_birthplace":       {"type": "string", "description": "Место рождения"},
            "tenant_gender":           {"type": "string", "description": "Пол: М или Ж"},
            "passport_series":         {"type": "string", "description": "Серия паспорта (4 цифры)"},
            "passport_number":         {"type": "string", "description": "Номер паспорта (6 цифр)"},
            "passport_issued_date":    {"type": "string", "description": "Дата выдачи в формате ДД.ММ.ГГГГ"},
            "passport_issued_by":      {"type": "string", "description": "Кем выдан (наименование органа)"},
            "passport_division_code":  {"type": "string", "description": "Код подразделения в формате XXX-XXX"},
            "tenant_address":          {"type": "string", "description": "Адрес регистрации (со страницы прописки)"},
        },
        "required": [
            "tenant_full_name", "tenant_dob", "tenant_birthplace", "tenant_gender",
            "passport_series", "passport_number", "passport_issued_date",
            "passport_issued_by", "passport_division_code", "tenant_address",
        ],
    },
}

_SYSTEM_PROMPT = (
    "Ты — система распознавания паспортных данных. "
    "Читай данные точно как написано в документе. "
    "Если поле нечитаемо, размыто или частично закрыто — верни строку 'UNCLEAR'. "
    "Никогда не угадывай и не домысливай. "
    "Все 10 полей обязательны — используй 'UNCLEAR' если не можешь прочитать."
)
```

### Pattern 2: Image Download + Resize Pipeline

**What:** Download Telegram document file bytes via `bot.get_file()` + `.download_as_bytearray()`, resize via Pillow to max 1600px, encode to base64.

**Why resize:** A 4000x3000 smartphone photo consumes ~3200+ Claude tokens per image. Resizing to max 1600px on the longest edge preserves OCR-quality text while halving token cost. Official Anthropic recommendation: optimal size ≤ 1.15 megapixels.

```python
def _resize_image_bytes(raw_bytes: bytes, max_px: int = 1600) -> bytes:
    """Resize image so longest edge <= max_px. Returns JPEG bytes.

    Synchronous — wrap with asyncio.to_thread() from async callers.
    Preserves aspect ratio. No-op if image is already small enough.
    """
    img = Image.open(io.BytesIO(raw_bytes))
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
```

### Pattern 3: Two-Image Single API Call

**What:** Pass both passport images in one `messages.create()` call. Reduces latency vs. two sequential calls.

```python
async def extract_passport_fields(
    page1_bytes: bytes,
    page2_bytes: bytes,
) -> dict[str, str]:
    """Call Claude Vision with both passport pages. Returns 10-field dict.

    All values are strings. Fields the model cannot read are 'UNCLEAR'.
    Raises anthropic.APIError on network/auth failure.
    Raises ValueError if response does not contain tool_use block.
    """
    # Resize both images (synchronous Pillow in thread)
    page1_resized = await asyncio.to_thread(_resize_image_bytes, page1_bytes)
    page2_resized = await asyncio.to_thread(_resize_image_bytes, page2_bytes)

    page1_b64 = base64.standard_b64encode(page1_resized).decode()
    page2_b64 = base64.standard_b64encode(page2_resized).decode()

    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_KEY)

    response = await client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_PASSPORT_TOOL],
        tool_choice={"type": "tool", "name": "extract_passport_fields"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": page1_b64,
                        },
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": page2_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Первое изображение — главная страница паспорта (серия, номер, ФИО, дата рождения, место рождения, пол, кем выдан, дата выдачи, код подразделения). "
                            "Второе изображение — страница с пропиской (адрес регистрации). "
                            "Вызови инструмент extract_passport_fields со всеми 10 полями."
                        ),
                    },
                ],
            }
        ],
    )

    # Extract tool_use block
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_passport_fields":
            logger.info(
                "OCR complete. input_tokens=%d output_tokens=%d",
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return block.input  # type: ignore[return-value]

    raise ValueError(
        f"Claude did not return tool_use block. "
        f"stop_reason={response.stop_reason!r} "
        f"content={response.content!r}"
    )
```

### Pattern 4: UNCLEAR Field Detection

**What:** After receiving the dict, scan all 10 fields. Collect any that contain `"UNCLEAR"`. Return the dict plus a list of unclear field names. The FSM handler uses this list to display a warning in the confirmation message.

```python
PASSPORT_FIELDS = [
    "tenant_full_name", "tenant_dob", "tenant_birthplace", "tenant_gender",
    "passport_series", "passport_number", "passport_issued_date",
    "passport_issued_by", "passport_division_code", "tenant_address",
]

def get_unclear_fields(fields: dict[str, str]) -> list[str]:
    """Return list of field names whose value is 'UNCLEAR'."""
    return [k for k in PASSPORT_FIELDS if fields.get(k, "").strip().upper() == "UNCLEAR"]
```

### Pattern 5: Confirmation Message Formatter

**What:** Format the 10 fields as a readable Telegram message for the user to verify. Flag any UNCLEAR fields with a warning symbol.

```python
_FIELD_LABELS = {
    "tenant_full_name":       "ФИО",
    "tenant_dob":             "Дата рождения",
    "tenant_birthplace":      "Место рождения",
    "tenant_gender":          "Пол",
    "passport_series":        "Серия",
    "passport_number":        "Номер",
    "passport_issued_date":   "Дата выдачи",
    "passport_issued_by":     "Кем выдан",
    "passport_division_code": "Код подразделения",
    "tenant_address":         "Адрес регистрации",
}

def format_ocr_summary(fields: dict[str, str]) -> str:
    """Format OCR result as a Telegram-ready message with UNCLEAR warnings."""
    lines = ["*Данные паспорта — проверьте внимательно:*\n"]
    for key, label in _FIELD_LABELS.items():
        value = fields.get(key, "UNCLEAR")
        marker = " !" if value.strip().upper() == "UNCLEAR" else ""
        lines.append(f"*{label}:* {value}{marker}")
    return "\n".join(lines)
```

### Anti-Patterns to Avoid

- **Sync anthropic.Anthropic() inside async handler:** Blocks the entire event loop. Always use `anthropic.AsyncAnthropic()`.
- **Prompt-only JSON ("respond as JSON"):** Produces JSON most of the time but the SDK cannot guarantee it. Use `tool_use` with `tool_choice={"type": "tool", "name": "..."}` to force structured output.
- **Storing passport photo bytes in `context.user_data` persistently:** The FSM must delete photo bytes from `user_data` after OCR completes — they are privacy-sensitive and balloon the PicklePersistence file.
- **Passing raw un-resized smartphone images:** 4K photos waste tokens and approach the 5 MB API limit. Always resize first.
- **Calling `client = anthropic.AsyncAnthropic()` once at module load:** Create per-call or store in a module-level singleton. Module-level is fine; avoid creating it inside every call if called frequently.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from LLM | Regex/parse prose Claude response | `tool_use` with JSON schema | Prose parsing is fragile; tool_use is API-enforced |
| Image resize | Custom pixel math | `Pillow Image.thumbnail()` | Already installed; handles EXIF rotation, LANCZOS downsampling |
| Async HTTP download | Manual socket code | `bot.get_file().download_as_bytearray()` | python-telegram-bot built-in; handles auth token automatically |
| Retry on API error | Manual retry loop | anthropic SDK handles retries | SDK has built-in retry with exponential backoff |

**Key insight:** The entire OCR service is a thin wrapper. The complexity lives in the prompt and schema design, not in custom code.

---

## Common Pitfalls

### Pitfall 1: Telegram Photo vs Document Compression (CRITICAL)

**What goes wrong:** User sends passport as a photo (via the camera/gallery button). Telegram compresses it to JPEG ~1280px max. Claude then works on blurry text — especially hurts the registration address page which has dense small print.

**How to avoid:** In the FSM passport upload states, accept `filters.Document.IMAGE` (not `filters.PHOTO`). If a `PHOTO` update arrives, respond with an explicit instruction: "Пожалуйста, отправьте фото как файл: Прикрепить → Файл (не как фотографию)." Log the warning.

**Handler filter:**
```python
# In ConversationHandler states:
PASSPORT_PAGE1: [
    MessageHandler(filters.Document.IMAGE, handle_passport_page1),
    MessageHandler(filters.PHOTO, handle_passport_wrong_type),   # warn user
],
```

**Warning signs:** OCR returns garbled passport series/number. `update.message.document` is None while `update.message.photo` is not None.

### Pitfall 2: Claude Hallucination on Unclear Fields

**What goes wrong:** Claude returns a plausible but wrong value (e.g., dob `15.06.1987` instead of `15.08.1987`) for a blurry or low-quality photo. No error is raised — the wrong data silently enters the contract.

**How to avoid:**
1. Include UNCLEAR instruction in both system prompt and tool description.
2. Use `tool_choice={"type": "tool", "name": "extract_passport_fields"}` to force the tool call — prevents Claude from adding a prose caveat block that might omit some fields.
3. Show the confirmation screen (OCR-04) prominently with per-field display. The human is the last safety net.
4. Log `input_tokens` and `output_tokens` for every OCR call to detect unexpectedly high usage (may indicate a large un-resized image).

### Pitfall 3: 5 MB API Limit Per Image

**What goes wrong:** A modern smartphone HEIC photo converted to JPEG can exceed 5 MB. The Anthropic API rejects images over 5 MB with a 400 error.

**How to avoid:** The `_resize_image_bytes()` resize to max 1600px virtually guarantees output under 1 MB for a JPEG at quality=92. Log the byte size before sending.

**Detection:** `anthropic.BadRequestError` with message about image size.

### Pitfall 4: tool_use Block Not in Response

**What goes wrong:** In rare edge cases (model refusal, safety filter triggered on a passport photo, or very short `max_tokens`), Claude may not emit a `tool_use` block even when `tool_choice` is set.

**How to avoid:** Always check `response.stop_reason`. If it is not `"tool_use"`, log the full response and raise `ValueError`. Set `max_tokens` to at least 1024 (the schema is ~400 tokens; 1024 is safe headroom).

### Pitfall 5: Blocking Event Loop with Pillow

**What goes wrong:** `Image.open()` and `img.save()` are synchronous. Calling them directly in an async handler stalls the bot's event loop during resize.

**How to avoid:** Wrap `_resize_image_bytes` with `asyncio.to_thread()`:
```python
page1_resized = await asyncio.to_thread(_resize_image_bytes, page1_bytes)
```

### Pitfall 6: PicklePersistence Bloat from Photo Bytes

**What goes wrong:** If passport photo bytes (`bytes` ~500KB each) are stored in `context.user_data` and the conversation is persisted via PicklePersistence, every bot checkpoint writes ~1 MB of binary data. Over time this slows down pickle saves.

**How to avoid:** Delete photo bytes from `user_data` immediately after OCR completes:
```python
context.user_data.pop("passport_page1_bytes", None)
context.user_data.pop("passport_page2_bytes", None)
```

---

## Code Examples

### Complete `extract_passport_fields` call (condensed reference)

```python
# Source: anthropic SDK 0.86.0 tool_use pattern + official Anthropic Vision docs
async def extract_passport_fields(page1_bytes: bytes, page2_bytes: bytes) -> dict[str, str]:
    page1_b64 = base64.standard_b64encode(
        await asyncio.to_thread(_resize_image_bytes, page1_bytes)
    ).decode()
    page2_b64 = base64.standard_b64encode(
        await asyncio.to_thread(_resize_image_bytes, page2_bytes)
    ).decode()

    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_PASSPORT_TOOL],
        tool_choice={"type": "tool", "name": "extract_passport_fields"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": page1_b64}},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": page2_b64}},
                {"type": "text", "text": "Extract all 10 passport fields using the tool."},
            ],
        }],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise ValueError(f"No tool_use block in response: {response.stop_reason}")
```

### Download Telegram document bytes

```python
# Source: python-telegram-bot 22.x official API
async def _download_document_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bytes:
    """Download a document attachment and return raw bytes."""
    document = update.message.document
    tg_file = await context.bot.get_file(document.file_id)
    return bytes(await tg_file.download_as_bytearray())
```

### FSM state handlers (OCR-01 and OCR-02)

```python
async def handle_passport_page1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """OCR-01: Receive first passport page (document upload)."""
    context.user_data["passport_page1_bytes"] = await _download_document_bytes(update, context)
    await update.message.reply_text(
        "Страница 1 получена. Теперь отправьте страницу с пропиской (также как файл)."
    )
    return PASSPORT_PAGE2


async def handle_passport_page2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """OCR-02 + OCR-03: Receive second passport page, run OCR, show confirmation."""
    context.user_data["passport_page2_bytes"] = await _download_document_bytes(update, context)

    await update.message.reply_text("Распознаю паспортные данные...")

    try:
        fields = await extract_passport_fields(
            context.user_data["passport_page1_bytes"],
            context.user_data["passport_page2_bytes"],
        )
    except Exception as exc:
        logger.error("OCR failed: %s", exc)
        await update.message.reply_text(
            "Ошибка распознавания. Попробуйте загрузить фото ещё раз."
        )
        return PASSPORT_PAGE1  # loop back

    # Clean up raw photo bytes from user_data (privacy + size)
    context.user_data.pop("passport_page1_bytes", None)
    context.user_data.pop("passport_page2_bytes", None)

    context.user_data["passport_fields"] = fields
    unclear = get_unclear_fields(fields)

    summary = format_ocr_summary(fields)
    if unclear:
        summary += f"\n\n*Не удалось распознать {len(unclear)} поле(й). Проверьте и исправьте при необходимости.*"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Подтвердить", callback_data="ocr_confirm")],
        [InlineKeyboardButton("Загрузить заново", callback_data="ocr_retry")],
    ])
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=keyboard)
    return PASSPORT_CONFIRM  # OCR-04
```

### Wrong upload type handler (Pitfall 1 mitigation)

```python
async def handle_passport_wrong_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent a compressed photo instead of a document — instruct correctly."""
    await update.message.reply_text(
        "Пожалуйста, отправьте фото паспорта как файл, а не как фотографию.\n\n"
        "Как это сделать: нажмите скрепку → «Файл» → выберите фото паспорта."
    )
    return PASSPORT_PAGE1  # stay in same state
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parse Claude prose for JSON | `tool_use` with `tool_choice` forced | Anthropic tools API ~2024 | Eliminates JSON parse errors entirely |
| Tesseract + preprocessing | Claude Vision API | 2023+ | Far higher accuracy on Russian documents, zero preprocessing code |
| Resize after download | Resize before base64-encode | Best practice | Reduces API token usage 4x for 4K images |

**Deprecated/outdated:**
- `response_format` JSON mode: Claude-specific "respond as JSON" prompt — fragile. Replaced by `tool_use`.
- `anthropic.Anthropic()` sync client in async code: Blocks event loop. Always `AsyncAnthropic`.

---

## Field Mapping: ContractData vs OCR Output

The OCR service must return field names that map directly to `ContractData` fields in `models.py`. Verified mapping:

| OCR tool field key | ContractData field | Type after parsing |
|--------------------|--------------------|-------------------|
| `tenant_full_name` | `tenant_full_name` | `str` |
| `tenant_dob` | `tenant_dob` | `datetime.date` (parse `DD.MM.YYYY`) |
| `tenant_birthplace` | `tenant_birthplace` | `str` |
| `tenant_gender` | `tenant_gender` | `str` ("М" or "Ж") |
| `passport_series` | `passport_series` | `str` (4 digits) |
| `passport_number` | `passport_number` | `str` (6 digits) |
| `passport_issued_date` | `passport_issued_date` | `datetime.date` (parse `DD.MM.YYYY`) |
| `passport_issued_by` | `passport_issued_by` | `str` |
| `passport_division_code` | `passport_division_code` | `str` ("XXX-XXX") |
| `tenant_address` | `tenant_address` | `str` |

**Important:** OCR service returns all values as strings. The FSM confirmation handler is responsible for converting `tenant_dob` and `passport_issued_date` from `DD.MM.YYYY` strings to `datetime.date` objects using `validators.validate_date()` before assembling `ContractData`. This conversion should happen at ContractData assembly time (after user confirmation), not inside `ocr_service.py`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| anthropic Python SDK | OCR API calls | Yes (requirements.txt) | 0.86.0 | — |
| Pillow | Image resize | Yes (requirements.txt) | 11.2.1 | — |
| httpx | File download | Yes (requirements.txt) | 0.28.1 | — |
| ANTHROPIC_API_KEY env var | AsyncAnthropic client | Assumed set (validated by config.validate()) | — | Fails at startup without it |
| Internet access to api.anthropic.com | OCR calls | Required (server assumed online) | — | No fallback |

**Missing dependencies with no fallback:** None — all required Python packages are already installed.

**Note:** This phase does not require LibreOffice, SQLite, or Telegram API access in `ocr_service.py` itself. It is a pure async function module.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 + pytest-asyncio 0.25.3 |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| Quick run command | `python -m pytest tests/test_ocr_service.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OCR-01 | Document upload accepted, photo type rejected with correct message | unit (handler logic) | `pytest tests/test_ocr_service.py::TestDocumentFilter -x` | No — Wave 0 |
| OCR-02 | Second page bytes stored, both images passed to API | unit (mock API) | `pytest tests/test_ocr_service.py::TestExtractFields -x` | No — Wave 0 |
| OCR-03 | All 10 fields extracted with correct key names | unit (mock API response) | `pytest tests/test_ocr_service.py::TestExtractFields::test_all_fields_returned` | No — Wave 0 |
| OCR-03 | UNCLEAR returned when model returns UNCLEAR | unit | `pytest tests/test_ocr_service.py::TestExtractFields::test_unclear_passthrough` | No — Wave 0 |
| OCR-03 | ValueError raised when no tool_use block in response | unit | `pytest tests/test_ocr_service.py::TestExtractFields::test_missing_tool_use_raises` | No — Wave 0 |
| OCR-04 | Confirmation message contains all 10 field labels in Russian | unit | `pytest tests/test_ocr_service.py::TestFormatSummary` | No — Wave 0 |
| OCR-04 | UNCLEAR fields flagged with warning marker in summary | unit | `pytest tests/test_ocr_service.py::TestFormatSummary::test_unclear_marked` | No — Wave 0 |
| OCR-05 | Confirm callback stores fields in user_data | unit (mock) | `pytest tests/test_ocr_service.py::TestConfirmHandler` | No — Wave 0 |
| OCR-05 | Retry callback returns to PASSPORT_PAGE1 state | unit (mock) | `pytest tests/test_ocr_service.py::TestConfirmHandler::test_retry_returns_page1_state` | No — Wave 0 |
| OCR-03 | Image resize reduces bytes before encoding (Pillow) | unit | `pytest tests/test_ocr_service.py::TestResizeImage` | No — Wave 0 |

### Test Strategy

**Mock the Anthropic API** — do not make real API calls in unit tests. Use `unittest.mock.AsyncMock` to mock `client.messages.create()`. The mock returns a fake response object with a `content` list containing a `ToolUseBlock`.

**Integration test (optional, manual-only):** One test marked `@pytest.mark.integration` that calls the real Anthropic API with a sample passport image. Skip this test in CI: `@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="requires real API key")`.

**Pattern from existing tests:** Follow the same `sys.path.insert(0, ...)` pattern used in `test_document_service.py`. No conftest.py exists yet — create one for shared OCR test fixtures (mock image bytes).

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_ocr_service.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ocr_service.py` — covers OCR-01 through OCR-05
- [ ] `tests/conftest.py` — shared fixtures: `sample_image_bytes()`, `mock_anthropic_response()`, `passport_fields_fixture()`
- [ ] No framework install needed — pytest and pytest-asyncio already installed

---

## Open Questions

1. **Prompt iteration against real passport samples**
   - What we know: The system prompt and UNCLEAR instruction are solid for typical passports. Russian passport layouts are fairly standardized (main page: series/number in top right, MRZ at bottom; registration page: address block).
   - What's unclear: Whether the model reliably reads the `код подразделения` (subdivision code) which appears in small print near the issuing authority. This field has unusual formatting (XXX-XXX) and may need extra emphasis in the prompt.
   - Recommendation: Budget one real-sample test during implementation. If `passport_division_code` consistently comes back UNCLEAR, add a specific prompt note: "Код подразделения — это шестизначный код формата XXX-XXX, расположен под строкой 'Кем выдан'."

2. **ContractData assembly after user edits**
   - What we know: OCR-05 allows the user to confirm or reject. The REQUIREMENTS mention only confirm/reject, not field-by-field editing (that is v2 UX-01).
   - What's unclear: If all 10 fields are confirmed as-is, ContractData assembly is straightforward. If the user rejects (re-upload), the loop returns cleanly to PASSPORT_PAGE1. There is no partial edit flow in v1.
   - Recommendation: Implement confirm/re-upload only. Do not add per-field edit in Phase 4. Leave that for Phase 5/UX-01.

3. **Photo type detection completeness**
   - What we know: `filters.Document.IMAGE` matches documents with MIME type image/jpeg or image/png. `filters.PHOTO` matches inline photo messages.
   - What's unclear: Does `filters.Document.IMAGE` match WebP or HEIC documents? Modern iPhones send HEIC. Pillow can open both.
   - Recommendation: Accept `filters.Document.ALL` (not just `.IMAGE`) and let Pillow handle the format. If Pillow cannot open the file, catch `PIL.UnidentifiedImageError` and return a user-friendly error.

---

## Project Constraints (from CLAUDE.md)

The CLAUDE.md does not define a formal `## Constraints` section with enforcement rules, but the GSD workflow section mandates using GSD entry points for all file changes. The following constraints are derived from the project's established patterns:

| Constraint | Source | Rule |
|------------|--------|------|
| Async Anthropic client only | ARCHITECTURE.md anti-pattern | `AsyncAnthropic`, never `Anthropic` sync client |
| Result-style returns for validators | Phase 02 decision (STATE.md) | Return `value | str`; callers use `isinstance(result, str)` to detect errors |
| stdlib only for validators | Phase 02 decision (STATE.md) | OCR service may use anthropic SDK; the date parsing helper must use stdlib `datetime` |
| config.validate() placement | Phase 01 decision (STATE.md) | `ANTHROPIC_KEY` accessed via `config.ANTHROPIC_KEY`, never `os.getenv()` directly in service modules |
| Pinned dependencies with `==` | Phase 01 decision (STATE.md) | If any new package is added, pin with `==` in requirements.txt |
| No new dependencies | Phase 4 (all packages already installed) | Pillow 11.2.1 and anthropic 0.86.0 already in requirements.txt |
| Passport images as documents | Roadmap decision (STATE.md) | `filters.Document.IMAGE` (not `filters.PHOTO`); warn user if photo type received |
| No persistent storage of passport photos | ARCHITECTURE.md anti-pattern | Delete bytes from `user_data` after OCR call; never write photo files to disk |
| Logger via `logging.getLogger(__name__)` | Existing modules pattern | Consistent with `document_service.py`, `validators.py` |
| Top-level module files | Existing project structure | `ocr_service.py` at project root, not nested in a subpackage |

---

## Sources

### Primary (HIGH confidence)
- `models.py` in this repo — ContractData dataclass, exact field names and types verified
- `config.py` in this repo — `ANTHROPIC_KEY` constant confirmed
- `document_service.py` in this repo — established async service pattern (`asyncio.to_thread`, module-level logger, no subpackage)
- `.planning/research/STACK.md` — anthropic 0.86.0, tool_use structured output, image base64 encoding pattern
- `.planning/research/PITFALLS.md` — Telegram compression (Pitfall 1), hallucination UNCLEAR strategy (Pitfall 5), token cost from large images (Pitfall 7)
- `.planning/research/ARCHITECTURE.md` — OCR data path diagram, AsyncAnthropic anti-pattern explicitly documented
- `requirements.txt` — Pillow 11.2.1, anthropic 0.86.0, httpx 0.28.1 all confirmed installed
- `pyproject.toml` — pytest asyncio_mode=auto confirmed

### Secondary (MEDIUM confidence)
- Anthropic Vision API docs (referenced in STACK.md) — 5 MB image limit, optimal ≤1.15MP, base64 pattern
- Anthropic tool_use docs (referenced in STACK.md) — `tool_choice` forced call, `input_schema` JSON schema format

### Tertiary (LOW confidence)
- None — all findings verified from project files or prior HIGH-confidence research

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages confirmed installed, versions pinned in requirements.txt
- Architecture: HIGH — follows established document_service.py pattern exactly; OCR data path verified in ARCHITECTURE.md
- Pitfalls: HIGH — sourced from dedicated PITFALLS.md with original research citations
- Tool_use API: HIGH — documented in STACK.md with citation to official Anthropic docs; pattern verified consistent with anthropic 0.86.0 SDK

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (30 days — anthropic SDK moves fast but 0.86.0 is pinned)
