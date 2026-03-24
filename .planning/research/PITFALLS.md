# Domain Pitfalls

**Domain:** Telegram bot + document automation + Claude Vision OCR
**Project:** Rent Contract Bot
**Researched:** 2026-03-24

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or broken core functionality.

---

### Pitfall 1: Telegram Compresses Photos Sent via `send_photo` — Destroys OCR Quality

**What goes wrong:** When a user sends a passport photo as a regular photo message (not as a file/document), Telegram's client automatically compresses it to JPEG at ~0.87 compression ratio and caps dimensions at 1280x1280 pixels. The bot receives a degraded image. Claude Vision then works on blurry text, increasing OCR error rate significantly for fine printed fields (series number, registration address).

**Why it happens:** Telegram distinguishes between "photo" uploads (compressed, displayed inline) and "document/file" uploads (sent as-is). Most users instinctively tap the photo attachment button, not the file attachment button.

**Consequences:** Passport fields that contain small or dense text (especially the registration page with the address) get misread. This produces contracts with wrong passport data — a serious legal problem.

**Prevention:**
- Instruct the user explicitly in the bot dialog to use "Attach as File" (not as photo). Phrase it as: "Отправьте фото паспорта как файл (Прикрепить → Файл), иначе качество будет недостаточным."
- In the bot handler, accept both `photo` and `document` message types. If `photo` is received, respond with a warning message and ask to resend as a document.
- When receiving via `document`, use `get_file()` and download the original bytes before sending to Claude Vision.

**Detection (warning signs):**
- OCR results contain garbled or truncated passport series numbers.
- The bot receives `photo` update type instead of `document` type.

**Phase:** OCR integration phase (passport upload handler implementation).

---

### Pitfall 2: python-docx Placeholder Split Across Multiple XML Runs

**What goes wrong:** When a DOCX template is edited in Microsoft Word, Word silently splits what looks like a single text block into multiple XML `<w:r>` (run) elements. A placeholder like `[ФИО_АРЕНДАТОРА]` can be stored as three runs: `[ФИО_`, `АРЕНДАТОРА`, `]`. A naive `paragraph.text.replace()` or iterating `paragraph.runs[i].text` finds nothing because no single run contains the full placeholder string.

**Why it happens:** Word inserts run boundaries when spell-check, autocorrect, grammar correction, formatting changes, or IME composition touch the text. It is not visible to the document author but is present in the XML.

**Consequences:** Silent substitution failure — the placeholder literally stays in the output PDF with the bracket notation visible. The contract is invalid and the failure is not caught at runtime because `str.replace()` on a missing needle is a no-op.

**Prevention:**
- Use `docxtpl` (python-docx-template) with Jinja2-style `{{ FIELD_NAME }}` placeholders instead of raw python-docx `.replace()`. `docxtpl` handles run merging internally and is purpose-built for this problem.
- If staying with `[FIELD]` bracket format (as per current PROJECT.md), implement a run-merging preprocessing step: iterate all paragraphs, merge adjacent runs inside the same paragraph into a single run before substitution.
- After saving the DOCX template, open the raw XML (`unzip template.docx; cat word/document.xml`) and verify no placeholder is split across `</w:r><w:r>` boundaries. Do this once per template.
- Add a post-fill validation step: open the filled DOCX and verify no `[` character remains in any paragraph text.

**Detection (warning signs):**
- Generated PDF contains literal `[НАЗВАНИЕ_ПОЛЯ]` text.
- `document.paragraphs[i].text` shows the full placeholder but `runs[j].text` for any single run does not.

**Phase:** DOCX template filling implementation. Must be caught before any end-to-end test.

---

### Pitfall 3: LibreOffice Headless Font Substitution Breaks DOCX Layout

**What goes wrong:** Linux servers typically do not ship with Microsoft fonts (Calibri, Cambria, Times New Roman). LibreOffice substitutes them with Liberation fonts. Liberation fonts are metrically different — character widths differ slightly. This causes text to overflow cells, tables to reflow, line breaks to shift, and the resulting PDF to look visually broken compared to the original DOCX template.

**Why it happens:** DOCX templates created in Microsoft Word on Windows/Mac use Microsoft-proprietary fonts. The `fontconfig` system on Linux finds no match and picks the closest substitute automatically, without warning.

**Consequences:** Contracts with misaligned signature blocks, overflowing table cells, or text spilling outside borders. The PDF is technically valid but aesthetically and legally problematic for a printed document.

**Prevention:**
- Install `fonts-crosextra-carlito` and `fonts-crosextra-caladea` packages on the Ubuntu server. These are metrically compatible replacements for Calibri and Cambria respectively.
- Run the full conversion pipeline during project setup and visually compare the PDF against a locally-generated version. Do not defer font validation to production.
- Alternatively, embed fonts in the DOCX template using Word's "Embed fonts in the file" option before saving templates.
- Command: `sudo apt-get install fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation`

**Detection (warning signs):**
- Generated PDF has text cutoff at table cell boundaries.
- Running `fc-list | grep -i calibri` on the server returns empty.
- LibreOffice conversion log (redirect stderr) mentions font substitution.

**Phase:** Deployment setup / infrastructure phase. Must be verified before any PDF output is considered correct.

---

### Pitfall 4: ConversationHandler State Lost on Bot Restart

**What goes wrong:** By default, `ConversationHandler` in python-telegram-bot stores conversation state in memory only. When the bot process restarts (server reboot, code deployment, crash), all in-progress conversations are reset to the initial state. A user mid-way through filling passport data gets no error — the bot just silently ignores their next message or restarts the flow from the beginning.

**Why it happens:** The default `ConversationHandler` has no persistence backend. State lives in a Python dict that vanishes with the process.

**Consequences:** The landlord, who is the only user, loses all entered contract data if anything interrupts the bot mid-session. Must re-enter all fields from scratch.

**Prevention:**
- Use `PicklePersistence` or a custom `SQLitePersistence` backend. For this single-user bot, `PicklePersistence` is sufficient and requires no extra dependencies.
- Set `name='contract_conversation'` and `persistent=True` on the `ConversationHandler`.
- Store conversation data including partial OCR results in `context.user_data`, which is persisted automatically if `Application` is built with a persistence backend.
- Critical: `concurrent_updates` must be `False` when using `ConversationHandler` (this is also required for correctness, not just persistence).

**Detection (warning signs):**
- Bot resets to `/start` prompt after process restart.
- Any deployment without `PicklePersistence` configured.

**Phase:** Core bot/FSM implementation phase.

---

### Pitfall 5: Claude Vision Hallucination on Low-Quality or Rotated Passport Photos

**What goes wrong:** Claude Vision, when presented with a blurry, rotated, partially occluded, or poorly lit passport photo, does not return an error — it returns a confident-looking response with plausible but invented values. A field like "дата рождения" might be read as `15.06.1987` when the actual value is `15.08.1987`. The bot has no way to detect this automatically.

**Why it happens:** Large multimodal models are trained to be helpful. When uncertain about a character, they make the statistically most likely choice (OCR hallucination). This is especially pronounced for digits that look similar (0/6, 1/7, 3/8) in hand-stamped or low-resolution passports.

**Consequences:** A legally binding contract is generated with wrong personal data (wrong date of birth, wrong passport series). This creates legal problems for the landlord.

**Prevention:**
- Always include a "graceful degradation" instruction in the prompt: "If any field is unclear or illegible, respond with `UNCLEAR` for that field rather than guessing."
- Display the full parsed OCR result to the user in a confirmation step before generating the contract. The user (landlord) must visually verify each extracted field.
- Parse the structured JSON returned by Claude and flag any field containing `UNCLEAR` for manual entry.
- Require structured JSON output via the API (`response_format` or explicit JSON schema in prompt) to prevent free-form narrative that obscures errors.
- For the confirmation screen, format the data as a readable summary with each field on its own line for easy scanning.

**Detection (warning signs):**
- Claude returns narrative paragraphs instead of structured data (prompt needs stronger formatting instruction).
- Fields have similar character substitution errors (1/7, 0/6).
- User reports contract errors after the fact.

**Phase:** OCR + confirmation flow phase.

---

## Moderate Pitfalls

Issues that cause bugs, cost overruns, or poor UX but do not require rewrites.

---

### Pitfall 6: LibreOffice Headless Zombie Processes Under Concurrent Load

**What goes wrong:** Each `subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', ...])` call spawns a new LibreOffice process. If a previous conversion is still running (or crashed and left a lock file), the new call may fail or hang. Even for a single-user bot, if the user accidentally triggers two conversion requests in quick succession (double-tap), zombie soffice processes can accumulate.

**Why it happens:** LibreOffice is not designed as a server process. Each headless invocation initializes a full office suite environment. Lock files are left in `/tmp/` on crash.

**Prevention:**
- Wrap the `subprocess.run()` call with a timeout (e.g., 30 seconds). Kill the process and raise a user-friendly error if conversion exceeds that.
- Add cleanup for LibreOffice lock files in the error handler: `rm -f /tmp/.~lock.*`.
- Use `asyncio.to_thread()` to run the blocking subprocess without blocking the bot's event loop.
- Disable LibreOffice's first-run configuration dialogs: pass `--norestore --nofirststartwizard` flags.

**Detection (warning signs):**
- PDF conversion hangs indefinitely.
- `ps aux | grep soffice` shows multiple zombie processes.
- LibreOffice creates lock file at `/tmp/.~lock.*.docx#`.

**Phase:** PDF conversion implementation. Also deployment checklist.

---

### Pitfall 7: Anthropic API Token Cost Spike from Large Passport Images

**What goes wrong:** Claude Vision charges tokens based on image dimensions. A 4000x3000 pixel passport photo (common from modern smartphones) consumes approximately 3,200+ tokens per image. With two passport pages per contract, each OCR call costs ~6,400 image tokens plus prompt tokens. At high usage this compounds, but even for a personal-use bot, sending the original unresized image is wasteful.

**Why it happens:** Developers pass the raw `file_bytes` to the API without downscaling. Telegram downloads the original file when using `send_document`, so the full-resolution image is available.

**Prevention:**
- Resize the image before sending to the API. Target maximum 1600px on the longest edge — this preserves enough resolution for passport text OCR while keeping token count manageable.
- Use `Pillow` to resize: `Image.open(io.BytesIO(file_bytes)).thumbnail((1600, 1600))` before base64-encoding.
- Log the actual token usage from the API response (`usage.input_tokens`) during development to baseline costs.

**Detection (warning signs):**
- `usage.input_tokens` exceeds 5000 for a two-page passport OCR call.
- API billing dashboard shows unexpectedly high costs.

**Phase:** OCR integration phase.

---

### Pitfall 8: SQLAlchemy Async Session Misuse with SQLite in python-telegram-bot

**What goes wrong:** Using SQLAlchemy's async engine with SQLite (`aiosqlite`) while also running `concurrent_updates=False` in python-telegram-bot creates a subtle tension: the bot processes updates serially but the async session may still hold a write lock across `await` yield points. If any handler accidentally creates an async session and then `await`s inside a long operation (e.g., waiting for Claude API) while holding an uncommitted write transaction, SQLite's write lock is held for the entire duration.

**Why it happens:** SQLAlchemy async sessions are context-manager based but developers often open them too broadly (wrapping an entire handler function instead of individual DB operations).

**Prevention:**
- Keep SQLAlchemy sessions scoped tightly: open a session, write, commit, close — before any `await` calls to external APIs.
- Store OCR results and conversation state in `context.user_data` (in-memory, persisted via PicklePersistence) during the conversation. Only write to SQLite at contract finalization time, which is a single atomic operation.
- Use WAL mode for SQLite: `PRAGMA journal_mode=WAL` at connection initialization. This allows reads during a write and reduces lock contention.

**Detection (warning signs):**
- `sqlite3.OperationalError: database is locked` in logs.
- Contract saves intermittently fail.

**Phase:** Database integration phase.

---

### Pitfall 9: Contract Number Generation Race (Even for Single-User Bot)

**What goes wrong:** The contract number format `{group}/{apartment}/{date}` derived from the current date can produce duplicates if two contracts for the same apartment are created on the same day (e.g., a mistake was made and the landlord re-generates the contract). The DOCX is overwritten, the old contract is lost, and the SQLite record may fail a unique constraint.

**Why it happens:** The number generation schema has no sequence component — it relies on date uniqueness which is not guaranteed.

**Prevention:**
- Append a sequence suffix to the contract number: `{group}/{apartment}/{date}-{seq}` where `seq` starts at 1 and increments if the base number already exists in the DB.
- Alternatively, append a short UUID suffix (4 characters).
- Never overwrite existing contract files. Use the contract number as a directory or filename and check for existence before writing.

**Detection (warning signs):**
- `UNIQUE constraint failed` error in SQLite logs.
- Contract files in `storage/contracts/` get overwritten silently.

**Phase:** Contract generation and storage phase.

---

## Minor Pitfalls

Issues that cause UX friction or subtle bugs but are easy to fix once identified.

---

### Pitfall 10: Telegram File Download Fails Silently if Bot Token Changes

**What goes wrong:** `file_id` values returned by Telegram are tied to the specific bot token. If the bot token is rotated (e.g., after a security incident), all previously downloaded `file_id` values become invalid. In this project, passport photos are downloaded in the same handler session, so this is unlikely — but if any `file_id` is cached to disk and reused later, it will fail with a generic 400 error.

**Prevention:** Never persist `file_id` values across sessions for reuse. Always download the file immediately within the handler and store the raw bytes or the resulting document, not the Telegram file reference.

**Phase:** Photo handling implementation.

---

### Pitfall 11: ConversationHandler Does Not Handle Unexpected Input Gracefully by Default

**What goes wrong:** If the user sends an unexpected message type at a given state (e.g., sends a voice message when the bot expects a phone number), the `ConversationHandler` silently drops the update — no response, no error. The user sees a dead bot.

**Prevention:**
- Add a fallback handler to each state that responds with a contextual error message: "Пожалуйста, введите номер телефона в формате +7XXXXXXXXXX."
- Use `MessageHandler(filters.ALL, fallback_callback)` as the last entry in each state's handler list to catch unexpected input types.

**Phase:** Conversation flow implementation.

---

### Pitfall 12: LibreOffice `--outdir` and Working Directory Confusion

**What goes wrong:** When running `libreoffice --headless --convert-to pdf --outdir /path/to/output /path/to/input.docx`, LibreOffice may write the output PDF to an unexpected location if the `--outdir` path does not exist or if relative paths are used. The subprocess call returns exit code 0 (success) but the PDF is not where the bot looks for it.

**Prevention:**
- Always use absolute paths for both input DOCX and `--outdir`.
- After subprocess call, assert the expected output file exists: `assert output_pdf_path.exists()`, and raise a descriptive error if not.
- Create the output directory before calling LibreOffice: `output_dir.mkdir(parents=True, exist_ok=True)`.

**Phase:** PDF conversion implementation.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Bot FSM setup | State lost on restart | Add `PicklePersistence` from day one |
| Passport photo upload | Telegram compression destroys OCR quality | Require document upload, not photo upload |
| OCR prompt design | Claude hallucination on unclear fields | Structured JSON output + `UNCLEAR` fallback |
| DOCX template filling | Placeholder split across XML runs | Use `docxtpl` or validate template XML structure |
| PDF conversion | Missing fonts cause layout shift | Install Carlito/Caladea on server before testing |
| PDF conversion | LibreOffice zombie processes | Add subprocess timeout + lock file cleanup |
| Contract storage | Duplicate contract numbers on same day | Add sequence suffix to number generation |
| Database writes | SQLite lock held during async API calls | Scope sessions tightly; write only at finalization |

---

## Sources

- [ConversationHandler official docs (v22.5)](https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html) — concurrent_updates requirement, persistence prerequisites, nested conversation limitations
- [Making your bot persistent — PTB Wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent) — PicklePersistence setup
- [Claude Vision API docs](https://platform.claude.com/docs/en/build-with-claude/vision) — image token costs, OCR capabilities
- [Claude Vision for Document Analysis — GetStream](https://getstream.io/blog/anthropic-claude-visual-reasoning/) — hallucination on low-quality images, graceful degradation prompting
- [python-docx placeholder split issue #99](https://github.com/python-openxml/python-docx/issues/99) — run splitting root cause
- [Filling a docx template while preserving style](https://blog.xa0.de/post/Filling-a-docx-template-with-Python-while-preserving-style/) — run merging workaround
- [docxtpl PyPI](https://pypi.org/project/docxtpl/) — Jinja2 template alternative
- [LibreOffice Docker conversion guide — Medium](https://medium.com/@jha.aaryan/convert-docx-to-pdf-for-free-a-docker-libreoffice-implementation-guide-cca493831391) — font substitution, concurrency issues
- [LibreOffice deterministic conversion — Ask LibreOffice](https://ask.libreoffice.org/t/use-soffice-to-convert-from-docx-pdf-deterministically/34418) — headless stability concerns
- [Telegram image compression issue](https://github.com/telegramdesktop/tdesktop/issues/25676) — photo vs document upload compression behavior
- [Telegram Bot API file limits](https://core.telegram.org/bots/api) — send_photo 10MB vs send_document 50MB limits
- [aiosqlite for async SQLite](https://github.com/omnilib/aiosqlite) — async SQLite event loop integration
- [Using SQLite and asyncio effectively — Piccolo ORM](https://piccolo-orm.readthedocs.io/en/1.3.2/piccolo/tutorials/using_sqlite_and_asyncio_effectively.html) — WAL mode, transaction scoping
- [Anthropic API rate limits](https://platform.claude.com/docs/en/api/rate-limits) — token limits per tier
