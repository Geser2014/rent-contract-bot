<!-- GSD:project-start source:PROJECT.md -->
## Project

**Rent Contract Bot**

Telegram-бот для автоматизации создания договоров аренды квартир. Бот собирает данные через диалог, распознаёт паспорт арендатора через Claude Vision API, заполняет DOCX-шаблон и отправляет готовый PDF. Предназначен для арендодателя, управляющего двумя группами объектов (Г39 и Г38).

**Core Value:** Полный цикл создания договора аренды за 2-3 минуты вместо 25-40 минут ручной работы — от выбора квартиры до отправки готового PDF.

### Constraints

- **Tech stack**: Python 3.10+, python-telegram-bot 20.x (async), Anthropic Claude API, python-docx, SQLAlchemy + SQLite
- **PDF conversion**: LibreOffice headless (должен быть установлен на сервере)
- **AI model**: Claude Sonnet для OCR (баланс скорости и качества)
- **File size**: Максимум 10 MB для загружаемых фото паспорта
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ | Runtime | Required by python-telegram-bot 22.x. 3.11 or 3.12 preferred for performance gains. |
| python-telegram-bot | 22.7 | Telegram bot framework | De-facto standard; v20+ async rewrite; built-in FSM via ConversationHandler; no external state machine library needed. ApplicationBuilder pattern is clean and testable. |
| anthropic | 0.86.0 | Claude Vision API client | Official Anthropic SDK; handles retries, auth, and typed responses. Required for passport OCR via claude-sonnet-4-5 or claude-sonnet-4-6. |
| docxtpl | 0.20.2 | DOCX template rendering | Jinja2-based template engine for .docx files. Template designers work in Word, Python just fills variables — clean separation. Depends on python-docx internally. |
| SQLAlchemy | 2.0.48 | ORM + async SQLite access | 2.0 unified interface; async mode via `create_async_engine` + aiosqlite. Works natively with python-telegram-bot's asyncio event loop. |
| aiosqlite | 0.22.1 | Async SQLite driver | Required by SQLAlchemy async for SQLite. Bridges synchronous sqlite3 to asyncio via a background thread. Stable, no real alternative. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-docx | 1.2.0 | DOCX low-level manipulation | Transitive dependency of docxtpl; do not import directly unless low-level paragraph editing is needed. |
| pydantic | 2.12.5 | Input data validation | Use for validating all user inputs before insertion into the template: dates, phone numbers, email, amounts. Pydantic v2 is 5-50x faster than v1 due to Rust core. |
| python-dotenv | latest stable | Environment variable loading | Load `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY` from `.env`. Standard pattern; keeps secrets out of code. |
| httpx | latest stable | HTTP client | Already used by the anthropic SDK; also useful for downloading Telegram photos before base64-encoding them for Claude. Async-native. |
### System Dependencies (Non-Python)
| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| LibreOffice | 7.x+ (headless) | DOCX → PDF conversion | Best preservation of DOCX formatting. Invoked via `subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', out_dir, docx_path])`. Must be installed on the Ubuntu server. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| pytest + pytest-asyncio | Async test runner | python-telegram-bot handlers are all async; pytest-asyncio makes testing them trivial. |
| ruff | Fast linter + formatter | Replaces flake8 + black + isort in one tool. Extremely fast, zero config needed for standard projects. |
| python-dotenv | Dev `.env` loading | Same library used in prod; load secrets without committing them. |
## Installation
# Core runtime
# Dev dependencies
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| python-telegram-bot 22.x | aiogram 3.x | If you need webhook-first architecture, built-in FSM via Router+State, or are already an aiogram user. Both are async; aiogram has slightly better webhook performance but a steeper learning curve. |
| docxtpl | python-docx (direct) | If your template logic is trivial (no loops, no conditionals). For the rent contract use case with optional deposit fields and multi-part payments, docxtpl's Jinja2 conditionals are essential. |
| docxtpl | jinja2 + lxml | Never for DOCX. This approach breaks Word's XML namespace handling reliably. |
| LibreOffice headless | weasyprint / reportlab | Only if generating PDF from scratch (HTML→PDF). Does not preserve DOCX template formatting — defeats the purpose here. |
| LibreOffice headless | docx2pdf (Windows) | Linux-only use case here. docx2pdf requires Microsoft Word or LibreOffice anyway; just call LibreOffice directly. |
| SQLAlchemy 2.0 + aiosqlite | raw aiosqlite | Acceptable for very simple projects. SQLAlchemy adds migrations (Alembic), relationships, and typed models — worth it for maintaining contract history over time. |
| SQLAlchemy 2.0 + aiosqlite | PostgreSQL | PostgreSQL is overkill for a single-user bot with ~100 contracts/year. SQLite with WAL mode handles this load trivially. |
| anthropic SDK | openai + GPT-4V | Claude Sonnet has demonstrably better Russian document OCR quality, is explicitly recommended in PROJECT.md, and the structured output via tool_use makes JSON extraction cleaner than parsing prose. |
| pydantic v2 | marshmallow | Pydantic v2's Rust core is significantly faster; type-hint syntax requires less boilerplate; better IDE integration. No reason to use marshmallow for new Python projects. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| python-telegram-bot 13.x or 14.x | Pre-async versions; synchronous handlers block the event loop; deprecated since 2022. | python-telegram-bot 22.x |
| Updater class (deprecated) | Removed or heavily deprecated in v22; use ApplicationBuilder + `run_polling()` instead. | `ApplicationBuilder` + `app.run_polling()` |
| `python-docx` for template filling | Not designed for templates; requires manual XML surgery to replace placeholders; breaks formatting. | docxtpl |
| Tesseract / pytesseract | Poor accuracy on Russian handwriting and complex passport layouts; requires significant pre-processing tuning. | Claude Vision API (claude-sonnet-4-5 or claude-sonnet-4-6) |
| weasyprint / reportlab for PDF | No DOCX input; would require re-implementing the entire contract layout in Python. | LibreOffice headless |
| unoconv | Wrapper around LibreOffice that adds a server daemon; unnecessary complexity for single-user bots; call `libreoffice --headless` directly. | Direct subprocess call to `libreoffice` |
| asyncpg / PostgreSQL | Overkill for one user; adds infra complexity. | aiosqlite |
| telegram.Bot (raw API) | Low-level; requires manual update polling and handler routing; no FSM. Use only for custom webhook setups. | python-telegram-bot's `Application` class |
## Stack Patterns by Variant
- Download photo via `bot.get_file()` + httpx
- Encode with `base64.standard_b64encode()`
- Pass as `{"type": "base64", "media_type": "image/jpeg", "data": ...}` in Claude messages
- Extract to structured dict via Claude's `tool_use` feature for deterministic JSON output
- Use `{{variable}}` syntax in Word templates (docxtpl's Jinja2 style)
- Use `{% if deposit_split %}` blocks for conditional sections (e.g., split deposit)
- Call `doc.render(context_dict)` where context_dict contains all validated fields
- Write rendered .docx to a temp file
- Call `subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', '/tmp', docx_path], timeout=30)`
- Read resulting .pdf and send via `bot.send_document()`
- Clean up temp files in a `finally` block
- Define integer state constants (e.g., `SELECT_GROUP = 0`, `SELECT_APARTMENT = 1`)
- Use `ConversationHandler(entry_points=..., states={...}, fallbacks=[...])`
- Store partial form data in `context.user_data` dict throughout the conversation
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| python-telegram-bot 22.7 | Python 3.10–3.14 | Requires Python 3.10 minimum (confirmed on PyPI). |
| anthropic 0.86.0 | Python 3.9+ | Compatible with Python 3.10+. |
| SQLAlchemy 2.0.48 | aiosqlite 0.22.1 | SQLAlchemy 2.0+ required for async API; `create_async_engine("sqlite+aiosqlite:///...")` syntax. |
| docxtpl 0.20.2 | python-docx 1.2.0 | docxtpl installs python-docx as a dependency; do not pin python-docx separately unless forced by conflict. |
| pydantic 2.12.5 | Python 3.9+ | Pydantic v2 is NOT drop-in compatible with v1; if any dependency pulls in v1, pin pydantic>=2. |
## Model Selection for Claude Vision
- Sonnet tier gives the right balance of accuracy vs. cost for Russian passport text extraction
- Haiku is faster/cheaper but accuracy on handwritten fields in Russian passports is lower
- Opus is unnecessary for OCR — document extraction is a well-defined task, not complex reasoning
- Pass both passport images in a single API call (main page + registration page) to reduce latency
## Sources
- [PyPI: python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — v22.7, Python >=3.10 (HIGH confidence)
- [PyPI: anthropic](https://pypi.org/project/anthropic/) — v0.86.0, Python >=3.9 (HIGH confidence)
- [PyPI: docxtpl](https://pypi.org/project/docxtpl/) — v0.20.2, requires python-docx + jinja2 (HIGH confidence)
- [PyPI: SQLAlchemy](https://pypi.org/project/SQLAlchemy/) — v2.0.48 stable, v2.1.0b1 pre-release (HIGH confidence)
- [PyPI: aiosqlite](https://pypi.org/project/aiosqlite/) — v0.22.1 (HIGH confidence)
- [PyPI: python-docx](https://pypi.org/project/python-docx/) — v1.2.0 (HIGH confidence)
- [PyPI: pydantic](https://pypi.org/project/pydantic/) — v2.12.5 stable (HIGH confidence)
- [Anthropic Vision Docs](https://platform.claude.com/docs/en/build-with-claude/vision) — image formats (JPEG/PNG/GIF/WebP), 5 MB API limit, base64 encoding pattern (HIGH confidence)
- [python-telegram-bot examples v22.7](https://docs.python-telegram-bot.org/en/stable/examples.html) — ConversationHandler patterns (HIGH confidence)
- [WebSearch: docxtpl vs python-docx 2025](https://mlhive.com/2025/12/mastering-dynamic-word-document-generation-python-docxtpl) — docxtpl usage pattern confirmed (MEDIUM confidence)
- [WebSearch: LibreOffice headless subprocess 2025](https://tariknazorek.medium.com/convert-office-files-to-pdf-with-libreoffice-and-python-a70052121c44) — subprocess invocation pattern (MEDIUM confidence)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
