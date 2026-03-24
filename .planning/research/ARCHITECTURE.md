# Architecture Patterns

**Domain:** Telegram bot + document automation (contract generation with Vision OCR)
**Researched:** 2026-03-24
**Confidence:** HIGH — based on official python-telegram-bot docs, Anthropic Vision API docs, verified community patterns

---

## Recommended Architecture

Six discrete components. Each has a single responsibility. No component reaches across its boundary into another's internals.

```
┌─────────────────────────────────────────────────────┐
│                  Telegram Layer                      │
│   Updater → Application → ConversationHandler(FSM)  │
└───────────────────┬─────────────────────────────────┘
                    │ user_data (in-memory during session)
                    ▼
┌─────────────────────────────────────────────────────┐
│               Dialog / FSM Layer                     │
│   States: GROUP → APARTMENT → DATES → AMOUNTS →     │
│           CONTACTS → PASSPORT → CONFIRM → GENERATE  │
└───────┬───────────────────────┬─────────────────────┘
        │ validated fields       │ passport photos (bytes)
        ▼                       ▼
┌───────────────┐    ┌──────────────────────────────┐
│  Validation   │    │       OCR Service             │
│  Layer        │    │  (Anthropic Claude Vision)    │
│  (pure funcs) │    │  base64 encode → API call →  │
└───────┬───────┘    │  parse JSON response          │
        │             └──────────────┬───────────────┘
        │ clean data                 │ structured passport fields
        └────────────┬───────────────┘
                     │ ContractData (complete record)
                     ▼
┌─────────────────────────────────────────────────────┐
│            Document Generation Layer                 │
│  1. Load DOCX template from storage/templates/      │
│  2. Replace [PLACEHOLDER] tokens via python-docx    │
│  3. Write filled DOCX to tmp/                       │
│  4. Call LibreOffice headless subprocess → PDF      │
│  5. Clean up tmp DOCX, return PDF path              │
└───────────────────┬─────────────────────────────────┘
                    │ pdf_path + ContractData
                    ▼
┌─────────────────────────────────────────────────────┐
│              Persistence Layer                       │
│  SQLAlchemy + SQLite                                 │
│  Models: Contract (all fields + pdf_path + number)  │
│  Session scope: one session per contract creation   │
└─────────────────────────────────────────────────────┘
                    │ confirmation
                    ▼
           Back to Telegram Layer
           (send PDF to user)
```

---

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **Telegram Layer** (Application + Updater) | Receive updates, route to handlers, send replies | Telegram API events | Messages, documents | Dialog/FSM Layer |
| **Dialog/FSM Layer** (ConversationHandler) | Manage conversation state, collect fields, drive flow | Telegram messages/photos | Prompts to user, collected data | Validation Layer, OCR Service, Document Generation |
| **Validation Layer** | Validate individual fields (dates, phone, email, amounts, age) | Raw user strings | Validated values or error messages | Dialog/FSM Layer (called inline) |
| **OCR Service** | Send passport photos to Claude Vision, parse structured data | Image bytes (2 photos) | Dict of passport fields (name, DOB, passport number, registration address) | Dialog/FSM Layer |
| **Document Generation Layer** | Fill template, convert to PDF | ContractData dict, template path | PDF file path | Persistence Layer, Telegram Layer |
| **Persistence Layer** | Store completed contracts, generate contract numbers | ContractData + PDF path | Contract record with generated number | Document Generation Layer |

---

## Data Flow

### Full Contract Creation Flow

```
User sends /start
  │
  ▼
[FSM: STATE_GROUP]
  User selects Г39 or Г38 → stored in user_data["group"]
  │
  ▼
[FSM: STATE_APARTMENT]
  User selects apartment number → user_data["apartment"]
  │
  ▼
[FSM: STATE_DATES]
  User enters start/end dates → Validation → user_data["dates"]
  │
  ▼
[FSM: STATE_AMOUNTS]
  User enters rent + deposit (one-time or 50/50) → Validation → user_data["amounts"]
  │
  ▼
[FSM: STATE_CONTACTS]
  User enters tenant phone + email → Validation → user_data["contacts"]
  │
  ▼
[FSM: STATE_PASSPORT_PAGE1]
  User sends photo → bot.get_file() → download bytes → user_data["photo1"]
  │
  ▼
[FSM: STATE_PASSPORT_PAGE2]
  User sends photo → bot.get_file() → download bytes → user_data["photo2"]
  │
  ▼
OCR Service:
  base64(photo1) + base64(photo2) → Claude Sonnet API
  Prompt: "Extract passport data as JSON: {last_name, first_name, middle_name,
           birth_date, passport_series, passport_number, issued_by,
           issued_date, registration_address}"
  Response parsed → user_data["passport"]
  │
  ▼
[FSM: STATE_CONFIRM]
  Bot displays all collected data as formatted summary
  User confirms (Yes/Edit)
  │
  ▼ (on confirm)
[FSM: STATE_GENERATE]
  ContractData assembled from user_data
  → Document Generation Layer:
      Load storage/templates/{group}/{apartment}.docx
      Replace all [PLACEHOLDER] tokens
      Save to storage/tmp/{uuid}.docx
      subprocess: soffice --headless --convert-to pdf --outdir storage/tmp/ {docx}
      Delete tmp docx
  → Persistence Layer:
      Generate contract number: {group}/{apartment}/{YYYYMMDD}
      INSERT Contract record + pdf_path
  → Telegram Layer:
      bot.send_document(chat_id, open(pdf_path, 'rb'))
      Delete tmp pdf (optional — or keep for record)
```

### OCR Data Path (detail)

```
photo bytes
  → base64.b64encode().decode()
  → anthropic.messages.create(
        model="claude-sonnet-*",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ...}},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ...}},
                {"type": "text", "text": "Extract passport fields as JSON..."}
            ]
        }]
    )
  → response.content[0].text
  → json.loads()
  → dict of passport fields
```

Image constraints (HIGH confidence, official Anthropic docs):
- API limit: 5 MB per image
- Optimal size: no more than 1.15 megapixels (resize before sending if larger)
- Supported formats: JPEG, PNG, GIF, WebP
- Telegram photo downloads are JPEG — no conversion needed

---

## Patterns to Follow

### Pattern 1: FSM via ConversationHandler

**What:** Define each dialog step as a named integer state constant. Each state maps to one or more handlers (MessageHandler, CallbackQueryHandler). ConversationHandler routes incoming updates to the correct handler based on current state.

**When:** Any multi-step dialog where order and field collection matter.

**Example structure:**
```python
STATES = {
    GROUP: [CallbackQueryHandler(handle_group_selection)],
    APARTMENT: [CallbackQueryHandler(handle_apartment_selection)],
    DATES: [MessageHandler(filters.TEXT, handle_dates)],
    PASSPORT_PAGE1: [MessageHandler(filters.PHOTO, handle_passport_p1)],
    PASSPORT_PAGE2: [MessageHandler(filters.PHOTO, handle_passport_p2)],
    CONFIRM: [CallbackQueryHandler(handle_confirm)],
}

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states=STATES,
    fallbacks=[CommandHandler("cancel", cancel)],
    per_user=True,    # separate state per user
    per_chat=True,
)
```

**Rationale:** Built-in to python-telegram-bot 20.x, async-native, no extra dependency.

### Pattern 2: user_data as Session Scratchpad

**What:** ConversationHandler provides a `user_data` dict in CallbackContext that persists for the duration of a conversation. Accumulate fields here. Only write to DB when the complete record is assembled and confirmed.

**When:** Collecting multi-step form data before committing.

**Why:** Avoids partial DB writes. Keeps intermediate state in-memory where it belongs.

### Pattern 3: Thin Handlers, Fat Services

**What:** Handler functions (the callbacks registered in states) do only: extract the relevant value from update, call a service function, send the next prompt. All business logic lives in service modules.

**Structure:**
```
handlers/
    conversation.py   ← thin: extract, delegate, reply
services/
    ocr.py            ← Claude Vision API wrapper
    document.py       ← DOCX fill + PDF conversion
    validation.py     ← pure validation functions
    persistence.py    ← SQLAlchemy session management
```

**Why:** Handlers are hard to unit-test (require mocking Telegram). Services are plain Python — testable in isolation.

### Pattern 4: Subprocess for LibreOffice (fire-and-wait)

**What:** Run LibreOffice conversion synchronously using `asyncio.create_subprocess_exec` (not `subprocess.run`) so it doesn't block the async event loop.

**Why:** LibreOffice does not have a Python API. The subprocess approach is the standard pattern. Each conversion spawns a new process — acceptable for single-user personal bot. For high concurrency this would need a queue, but that's out of scope.

**Error handling note:** LibreOffice exits with code 0 even on failure. Check that the output PDF file exists after the subprocess completes rather than trusting the return code.

### Pattern 5: Separate tmp/ Directory with Cleanup

**What:** Write generated DOCX and PDF to `storage/tmp/{uuid}/`. After sending, delete the directory.

**Why:** Avoids filename collisions on concurrent requests (unlikely but safe). Makes cleanup trivial — just delete the directory. Final PDFs can optionally be archived to `storage/contracts/` keyed by contract number.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Passport Photos Permanently

**What:** Saving passport photo files to disk after OCR extraction.

**Why bad:** Privacy exposure. The raw bytes have served their purpose after OCR runs. SQLite stores the extracted text fields; the images don't need to persist.

**Instead:** Keep photos in-memory (user_data) during the session only. Delete after OCR call completes.

### Anti-Pattern 2: Blocking the Event Loop

**What:** Using `subprocess.run()` or synchronous `anthropic.Anthropic()` (blocking client) inside an async handler.

**Why bad:** python-telegram-bot 20.x is fully async. Blocking calls stall the entire bot for all users.

**Instead:** Use `asyncio.create_subprocess_exec()` for LibreOffice. Use `anthropic.AsyncAnthropic()` for Claude API calls.

### Anti-Pattern 3: One Giant Handler File

**What:** All conversation state handlers in one file.

**Why bad:** The conversation flow already has 8+ states. One file becomes unmaintainable.

**Instead:** One handler module per concern (conversation.py, document.py). States reference service functions.

### Anti-Pattern 4: Untyped ContractData

**What:** Passing raw `user_data` dict through the document generation pipeline.

**Why bad:** Missing keys fail silently at template fill time, not at validation time.

**Instead:** Use a `dataclass` or `TypedDict` for `ContractData`. Construct it at confirmation step from user_data, fail loudly if any required field is absent.

### Anti-Pattern 5: Synchronous LibreOffice without Timeout

**What:** Awaiting the LibreOffice subprocess with no timeout.

**Why bad:** LibreOffice can hang (especially on first cold start). The bot appears frozen with no error.

**Instead:** Use `asyncio.wait_for()` with a 30-60 second timeout. On timeout, kill the subprocess, send an error message.

---

## Build Order (Phase Dependencies)

Components have hard dependencies that dictate build sequence:

```
1. Project scaffold + config loading
   (everything else depends on this)
        │
        ▼
2. Validation Layer (pure functions, no deps)
   + Database models (SQLAlchemy schema)
   (can be built in parallel — neither depends on the other)
        │
        ▼
3. Document Generation Layer
   (depends on knowing what fields the template expects,
    which is defined by the DB schema / ContractData type)
        │
        ▼
4. OCR Service
   (depends on ContractData type to know what fields to extract)
        │
        ▼
5. Dialog / FSM Layer
   (depends on Validation, OCR Service, Document Generation)
        │
        ▼
6. Telegram Application wiring
   (depends on FSM Layer being complete)
        │
        ▼
7. End-to-end integration + error handling
   (all components exist, wire them together safely)
```

**Rationale for this order:**
- Validation and DB schema define the "shape" of data. Build them first so all downstream components agree on field names and types.
- Document generation can be developed and tested independently (load template → fill → convert) before the bot UI exists. This lets you verify LibreOffice integration without running Telegram.
- OCR service is a thin wrapper around the Anthropic API — build it after you know what fields you need from it.
- FSM layer is the integration point. Build it last so all services it calls already exist.

---

## Scalability Considerations

This is a single-user personal bot. Scalability is not a design driver. However:

| Concern | Current approach | If it becomes an issue |
|---------|-----------------|----------------------|
| LibreOffice startup latency | Cold start per conversion (~3-8s) | Keep a warm LibreOffice instance via `soffice --daemon` |
| Multiple simultaneous sessions | python-telegram-bot handles per-user isolation natively | Not applicable for personal use |
| Claude API rate limits | Single user, low volume | Not applicable |
| SQLite write contention | Single writer, personal use | Migrate to PostgreSQL |

---

## Directory Structure

```
rent-contract-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py               ← Application entry point
│   ├── handlers/
│   │   └── conversation.py   ← ConversationHandler setup + thin callbacks
│   ├── services/
│   │   ├── ocr.py            ← Claude Vision wrapper
│   │   ├── document.py       ← DOCX fill + LibreOffice PDF conversion
│   │   ├── validation.py     ← Pure validation functions
│   │   └── persistence.py    ← SQLAlchemy session + contract storage
│   ├── models/
│   │   ├── contract.py       ← SQLAlchemy ORM model
│   │   └── contract_data.py  ← ContractData dataclass (in-memory transfer object)
│   └── config.py             ← Env var loading (tokens, paths)
├── storage/
│   ├── templates/
│   │   ├── Г39/
│   │   │   └── {apartment}.docx
│   │   └── Г38/
│   │       └── {apartment}.docx
│   ├── tmp/                  ← Generated DOCX/PDF staging (gitignored)
│   └── contracts.db          ← SQLite database
└── tests/
    ├── test_validation.py
    ├── test_document.py
    └── test_ocr.py
```

---

## Sources

- [python-telegram-bot Architecture Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Architecture) — HIGH confidence, official docs
- [Anthropic Vision API Documentation](https://platform.claude.com/docs/en/build-with-claude/vision) — HIGH confidence, official docs (image limits: 5MB API, JPEG/PNG/GIF/WebP, optimal ≤1.15MP)
- [ConversationHandler Docs v13.x](https://docs.python-telegram-bot.org/en/v13.2/telegram.ext.conversationhandler.html) — HIGH confidence
- [LibreOffice headless conversion patterns](https://tariknazorek.medium.com/convert-office-files-to-pdf-with-libreoffice-and-python-a70052121c44) — MEDIUM confidence (verified against multiple sources)
- [python-docx-template (docxtpl)](https://docxtpl.readthedocs.io/) — HIGH confidence, official docs
- [SQLAlchemy Session Management](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) — HIGH confidence, official docs
