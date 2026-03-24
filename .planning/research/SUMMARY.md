# Project Research Summary

**Project:** Rent Contract Bot
**Domain:** Telegram bot — AI-powered passport OCR, DOCX template filling, PDF generation
**Researched:** 2026-03-24
**Confidence:** HIGH (stack and architecture), MEDIUM (features)

## Executive Summary

This is a personal landlord automation tool built as a Telegram bot: the user photographs tenant passport pages, Claude Vision extracts the data, a DOCX contract template is filled, and the PDF is delivered back in the same chat. The domain is narrow and well-understood — python-telegram-bot 22.x provides a built-in async FSM via ConversationHandler, docxtpl handles Jinja2-style template filling with Word documents, and LibreOffice headless converts DOCX to PDF. There are no exotic technology choices here; every component has official documentation and established community patterns.

The recommended implementation strategy is to build in strict layer order: scaffold and config first, then pure validation + DB schema, then document generation (testable without Telegram), then OCR service, then the FSM dialog layer that wires everything together. This order is dictated by architectural dependencies and allows each layer to be tested in isolation before integration. The core value is delivered when the complete cycle — group/apartment selection through PDF delivery — works end-to-end in under 3 minutes.

The key risks are all known and preventable. Telegram silently compresses photos, which degrades OCR accuracy: users must be forced to send passport images as files, not photos. Microsoft fonts are absent on Linux servers, which causes LibreOffice to produce misaligned PDFs: Carlito and Caladea font packages must be installed before any PDF output is considered valid. Claude Vision returns plausible-but-wrong data on unclear images without flagging uncertainty: every OCR result must pass through a human-review confirmation step, and the prompt must instruct the model to return `UNCLEAR` rather than guess. None of these risks require architectural changes — they require deliberate implementation choices at known phase boundaries.

---

## Key Findings

### Recommended Stack

All stack choices are conservative and high-confidence. python-telegram-bot 22.x is the de-facto standard for Python Telegram bots; its async rewrite (v20+) is fully asyncio-native, and ConversationHandler eliminates the need for any external state machine library. docxtpl is purpose-built for Jinja2-style template filling in Word documents — it handles the XML run-splitting problem that makes raw python-docx placeholder replacement unreliable. SQLAlchemy 2.0 with aiosqlite provides async SQLite access compatible with the bot's asyncio event loop. LibreOffice headless is the only viable DOCX-to-PDF converter that preserves formatting on Linux.

**Core technologies:**
- python-telegram-bot 22.7: async Telegram framework with built-in FSM — eliminates external state machine dependency
- anthropic 0.86.0: official Claude SDK for Vision API — use AsyncAnthropic client; claude-sonnet-4-5 or claude-sonnet-4-6 for Russian passport OCR
- docxtpl 0.20.2: Jinja2 template engine for DOCX — solves XML run-splitting problem inherent in raw python-docx replacement
- SQLAlchemy 2.0.48 + aiosqlite 0.22.1: async ORM for SQLite — session scoped per contract, WAL mode enabled
- pydantic 2.12.5: input validation — validate all user-entered fields at each FSM state before storing
- LibreOffice 7.x+ headless: DOCX-to-PDF conversion — only correct approach for preserving Word template formatting on Linux

**Critical version requirements:**
- Python 3.10+ (required by python-telegram-bot 22.x)
- Use `AsyncAnthropic()` not `Anthropic()` — synchronous client blocks the event loop
- Use `asyncio.create_subprocess_exec()` not `subprocess.run()` for LibreOffice calls

### Expected Features

The feature set is clear and well-bounded. There are no ambiguous priorities — all P1 features are needed before any v1 release. The differentiating features (split-deposit flow, SQLite history) are explicitly P2 and should not gate the initial delivery.

**Must have (table stakes — P1):**
- Guided step-by-step dialog (FSM) — any form-filling bot requires sequential question flow
- Group and apartment selection via inline keyboard — fixed inventory; free-text entry causes errors
- Passport OCR via Claude Vision (both pages) — core time-saving value proposition
- OCR result display with field-by-field correction — human-in-the-loop checkpoint; required for legal documents
- Confirmation screen before generation — prevents costly mistakes on irreversible action
- DOCX template fill per apartment — produces the contract; templates already designed per unit
- DOCX to PDF via LibreOffice headless — PDF is the expected deliverable format
- PDF delivered in Telegram — closes the loop without leaving the app
- Input validation at every FSM state (dates, phone, email, amounts) — prevents silent data corruption
- Contract number generation in group/apartment/date format — required for filing
- /cancel at any state — basic UX hygiene; users make mistakes mid-flow
- Error handling with user-readable messages — API failures must not surface stack traces

**Should have (differentiators — P2, add after v1 validation):**
- SQLite contract history — add when landlord needs past-contract lookup
- Split-deposit flow (50%+50%) — landlord-specific business rule; not in MVP
- Structured logging to file — add when first production failure requires diagnosis
- Tenant age validation against passport birth date — prevents minor tenant contracts

**Defer (v2+):**
- Contract amendment templates — different document flow; very low frequency
- CSV/Excel export of contract history — only if SQLite inspection becomes insufficient
- Multiple authorized users — only if landlord hires an assistant

### Architecture Approach

The architecture is six discrete components with single responsibilities and clean boundaries. No component reaches into another's internals. The FSM layer is the integration point that calls all services; services are plain Python modules testable without Telegram. The data transfer object (`ContractData` dataclass) is the contract between layers — assembled at confirmation from `user_data` and passed through document generation and persistence. In-memory `user_data` accumulates fields during the session; SQLite is written only once at contract finalization.

**Major components:**
1. Telegram Layer (Application + ConversationHandler) — receives updates, routes to handlers, sends replies
2. Dialog/FSM Layer — manages state, collects fields, drives the conversation flow
3. Validation Layer (pure functions) — validates individual fields; called inline by FSM; fully unit-testable
4. OCR Service — wraps Claude Vision API; returns structured passport field dict; fails loudly on UNCLEAR fields
5. Document Generation Layer — fills DOCX template via docxtpl, converts to PDF via LibreOffice subprocess
6. Persistence Layer — SQLAlchemy/SQLite; stores completed contracts; scoped sessions; WAL mode

### Critical Pitfalls

1. **Telegram photo compression destroys OCR quality** — require document upload (not photo upload) at the passport steps; if `photo` type is received, reject with a resend instruction; see PITFALLS.md Pitfall 1
2. **DOCX placeholder split across XML runs** — use docxtpl with `{{ FIELD }}` syntax instead of raw python-docx replacement; validate template XML before production; see PITFALLS.md Pitfall 2
3. **LibreOffice font substitution breaks PDF layout** — install `fonts-crosextra-carlito`, `fonts-crosextra-caladea`, `fonts-liberation` on the Ubuntu server before any PDF output is considered valid; see PITFALLS.md Pitfall 3
4. **ConversationHandler state lost on bot restart** — configure `PicklePersistence` from day one; set `persistent=True` on the handler; see PITFALLS.md Pitfall 4
5. **Claude Vision hallucination on unclear passport photos** — prompt must instruct `UNCLEAR` for illegible fields; every OCR result requires landlord review before contract generation; see PITFALLS.md Pitfall 5

---

## Implications for Roadmap

Based on the build order specified in ARCHITECTURE.md and the pitfall phase warnings in PITFALLS.md, a 6-phase structure is recommended.

### Phase 1: Project Scaffold and Infrastructure
**Rationale:** Every other component depends on configuration loading, directory structure, and dependency installation. LibreOffice font installation must happen here, not at PDF generation time — deferring it causes invisible failures later.
**Delivers:** Working Python project with all dependencies installed, `.env` loaded, `storage/` directory structure, SQLite DB initialized, LibreOffice verified with Carlito/Caladea fonts, bot token validated
**Addresses:** Initial project setup; no features yet
**Avoids:** Pitfall 3 (font substitution) — fonts verified at setup, not discovered in production

### Phase 2: Validation Layer and Database Models
**Rationale:** These are pure-code components with no external dependencies. They define the "shape" of data (`ContractData`) that all downstream components use. Build them first so field names and types are agreed upon before any service is written.
**Delivers:** Pydantic validators for dates/phone/email/amounts, SQLAlchemy `Contract` model, `ContractData` dataclass, database initialization, full unit test coverage
**Addresses:** Data validation (table stakes), contract history storage foundation
**Avoids:** Pitfall 9 (duplicate contract numbers) — sequence logic designed here

### Phase 3: Document Generation Layer
**Rationale:** Can be built and tested entirely without Telegram. Tests can fill a template with fixture data and assert the PDF is produced correctly. This lets LibreOffice integration be verified in isolation — including font rendering — before any bot UI exists.
**Delivers:** docxtpl template fill with all apartment templates, LibreOffice subprocess conversion, temp file management with cleanup, PDF output verified against visual baseline
**Addresses:** DOCX template fill, PDF conversion, PDF delivery (file produced; delivery wired in Phase 6)
**Avoids:** Pitfall 2 (XML run splitting) — docxtpl used from the start; Pitfall 6 (LibreOffice zombie processes) — timeout and lock file cleanup implemented here

### Phase 4: OCR Service
**Rationale:** A thin wrapper around the Anthropic API, but the prompt engineering and structured output format must be designed carefully. Build after `ContractData` is defined so the extraction schema matches exactly what the template expects.
**Delivers:** `ocr.py` service that accepts two image byte strings, calls Claude Vision with structured JSON prompt, returns validated passport field dict, flags UNCLEAR fields for manual correction
**Addresses:** Passport OCR (both pages), OCR result review (UNCLEAR flag handling)
**Avoids:** Pitfall 5 (Claude hallucination) — UNCLEAR fallback in prompt; Pitfall 7 (token cost spike) — Pillow resize to max 1600px before API call

### Phase 5: FSM Dialog Layer
**Rationale:** The integration point. All services it calls (Validation, OCR, Document Generation) already exist and are tested. Build the FSM last so handler functions are thin wrappers around proven service calls.
**Delivers:** Full ConversationHandler with all states (GROUP → APARTMENT → DATES → AMOUNTS → CONTACTS → PASSPORT_PAGE1 → PASSPORT_PAGE2 → CONFIRM → GENERATE), PicklePersistence configured, per-state fallback handlers for unexpected input types, /cancel at all states
**Addresses:** All P1 table stakes features — guided dialog, apartment selection, confirmation screen, contract number generation, /cancel
**Avoids:** Pitfall 1 (photo compression) — document upload required, photo type rejected with instruction; Pitfall 4 (state lost on restart) — PicklePersistence from day one; Pitfall 11 (silent unexpected input) — fallback handlers per state

### Phase 6: Integration, Error Handling, and End-to-End Testing
**Rationale:** Wire all layers together in `main.py`, add production-grade error handling at every external call boundary, and run a complete contract cycle to validate the full flow.
**Delivers:** `main.py` entry point, error handling wrappers on all external calls (Claude API, LibreOffice, Telegram send), structured logging, end-to-end test generating a real PDF contract
**Addresses:** Error handling with user-readable messages (table stakes), structured logging (P2)
**Avoids:** Pitfall 8 (SQLite lock during async API calls) — session scoping verified at integration time; Pitfall 10 (file_id caching) — never persist file IDs; Pitfall 12 (LibreOffice outdir confusion) — absolute paths asserted

### Phase Ordering Rationale

- Phases 1-2 establish the foundations that every later phase assumes (config, field definitions, DB schema).
- Phase 3 before Phase 5 because document generation is independently testable and validates the most complex infra dependency (LibreOffice + fonts) without needing a Telegram bot running.
- Phase 4 before Phase 5 because the OCR service defines the passport field extraction contract; FSM handlers just call it.
- Phase 5 is intentionally last among feature phases — it is the wiring layer, not the logic layer. Building it last means all handlers are thin and all tests exercise real service code.
- Phase 6 is integration-only — no new features, just wiring and error handling that requires all components to exist.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (OCR Service):** Prompt engineering for structured Russian passport extraction is the highest-uncertainty element. The exact prompt, JSON schema, and UNCLEAR handling strategy should be developed and tested against real passport photos before integration. Claude model behavior on edge cases (partial occlusion, hand stamps, registration page formatting variations) is not fully characterizable from documentation alone.
- **Phase 3 (Document Generation):** DOCX template structure must be validated against actual apartment templates. If templates use features incompatible with docxtpl (complex tables, tracked changes, embedded objects), the template approach may need adjustment.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Dependency installation and project scaffold follow standard Python project patterns.
- **Phase 2:** Pydantic validators and SQLAlchemy models are fully documented with stable APIs.
- **Phase 5:** ConversationHandler FSM is well-documented; patterns are confirmed in official examples.
- **Phase 6:** Error handling and logging are standard Python patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI; official SDK docs consulted; no experimental dependencies |
| Features | MEDIUM | No direct competitors at this exact scope; extrapolated from analogous tools; core features are clear, P2 features may shift based on usage |
| Architecture | HIGH | Based on official python-telegram-bot architecture docs, Anthropic Vision API docs, and verified community patterns; build order is logically derivable from dependencies |
| Pitfalls | HIGH | All critical pitfalls traced to specific, reproducible root causes with documented prevention strategies and linked sources |

**Overall confidence:** HIGH

### Gaps to Address

- **OCR prompt quality on real Russian passports:** Research confirms hallucination risk and UNCLEAR mitigation strategy, but actual prompt text needs iteration against real samples. Plan for 1-2 prompt revision cycles during Phase 4 before FSM integration.
- **Per-apartment template compatibility with docxtpl:** Templates were designed before this research. Each template must be opened and verified for Jinja2-compatible `{{ }}` placeholder syntax (or migrated from any `[PLACEHOLDER]` bracket syntax). Budget template migration time in Phase 3.
- **LibreOffice version on target Ubuntu server:** Research assumes LibreOffice 7.x+. The exact server version should be confirmed during Phase 1; older versions have known conversion differences.

---

## Sources

### Primary (HIGH confidence)
- [PyPI: python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — v22.7, Python >=3.10
- [PyPI: anthropic](https://pypi.org/project/anthropic/) — v0.86.0
- [PyPI: docxtpl](https://pypi.org/project/docxtpl/) — v0.20.2
- [PyPI: SQLAlchemy](https://pypi.org/project/SQLAlchemy/) — v2.0.48
- [PyPI: pydantic](https://pypi.org/project/pydantic/) — v2.12.5
- [Anthropic Vision API Documentation](https://platform.claude.com/docs/en/build-with-claude/vision) — image limits, base64 encoding, token costs
- [python-telegram-bot Architecture Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Architecture) — ConversationHandler patterns
- [Making your bot persistent — PTB Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent) — PicklePersistence setup
- [SQLAlchemy Session Management](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) — async session scoping
- [python-docx placeholder split issue #99](https://github.com/python-openxml/python-docx/issues/99) — XML run splitting root cause

### Secondary (MEDIUM confidence)
- [Claude Vision for Document Analysis — GetStream](https://getstream.io/blog/anthropic-claude-visual-reasoning/) — hallucination on low-quality images
- [LibreOffice headless conversion — Medium](https://tariknazorek.medium.com/convert-office-files-to-pdf-with-libreoffice-and-python-a70052121c44) — subprocess pattern, font substitution
- [Telegram Bot API file limits](https://core.telegram.org/bots/api) — photo vs document compression behavior
- [Using SQLite and asyncio effectively — Piccolo ORM](https://piccolo-orm.readthedocs.io/en/1.3.2/piccolo/tutorials/using_sqlite_and_asyncio_effectively.html) — WAL mode
- [Botman.one rental contract bot](https://botman.one/en/blog/post?post_id=82) — real-world feature set reference

### Tertiary (LOW confidence)
- [docxtpl usage pattern — mlhive.com](https://mlhive.com/2025/12/mastering-dynamic-word-document-generation-python-docxtpl) — confirmed against primary docxtpl docs
- [Contract AI Reliability Problem — Artificial Lawyer, Oct 2025](https://www.artificiallawyer.com/2025/10/23/contract-ais-reliability-problem-when-ai-gets-it-wrong/) — OCR correction flow necessity (informs design choice, not implementation)

---

*Research completed: 2026-03-24*
*Ready for roadmap: yes*
