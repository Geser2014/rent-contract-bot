# Phase 3: Document Generation - Research

**Researched:** 2026-03-24
**Domain:** DOCX template rendering (docxtpl/Jinja2) + LibreOffice headless PDF conversion
**Confidence:** HIGH

---

## Summary

Phase 3 produces a `DocumentService` (or equivalent module) that accepts a fully-populated `ContractData` object and returns an absolute path to a finished PDF. There is no Telegram interaction in this phase — it is a pure Python/subprocess layer sandwiched between the data layer (Phase 2) and the OCR/dialog layers (Phases 4-5).

The two primary technical problems are (1) filling a DOCX template using docxtpl's Jinja2 engine so that `{{ }}` placeholders are replaced correctly without XML run-splitting, and (2) invoking LibreOffice headless as an async subprocess so the conversion does not block python-telegram-bot's event loop. Both libraries are already pinned in `requirements.txt` and tested on the target stack.

The critical constraint carried forward from Phase 1 and the project blockers list is that existing DOCX templates currently use `[PLACEHOLDER]` bracket syntax. Before docxtpl can fill them, every template must be migrated to `{{ placeholder }}` Jinja2 syntax. This migration is part of Phase 3 scope. The templates live in `storage/templates/Г39/` and `storage/templates/Г38/` — both directories exist but contain no `.docx` files yet, meaning the migration task is writing the template(s), not converting existing ones.

**Primary recommendation:** Implement a single `document_service.py` module. It exposes one public async function — `generate_contract(data: ContractData) -> str` — that (1) generates a unique contract number, (2) fills the template with docxtpl, (3) converts to PDF via `asyncio.to_thread(subprocess.run, [...])`, (4) cleans up temp DOCX in a `finally` block, and returns the absolute PDF path.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOC-01 | System generates contract number in format `группа/квартира/дата` | Pitfall 9 documents uniqueness problem; research identifies sequence-suffix pattern to prevent same-day duplicates |
| DOC-02 | System fills DOCX template with dialog and OCR data | docxtpl 0.20.2 render() API verified; full ContractData → context mapping documented; Jinja2 syntax confirmed |
| DOC-03 | System converts filled DOCX to PDF via LibreOffice headless | asyncio.to_thread + subprocess.run pattern verified; absolute path requirement, output assertion, temp cleanup all documented |
</phase_requirements>

---

## Standard Stack

### Core (Phase 3 relevant subset)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| docxtpl | 0.20.2 | DOCX template fill with Jinja2 | Solves XML run-split problem that defeats raw python-docx. Already pinned in requirements.txt. |
| LibreOffice (system) | 7.x+ headless | DOCX → PDF conversion | Best formatting preservation; required system dep on Ubuntu server. Not installed in Windows dev env — see Environment Availability. |
| asyncio.to_thread | stdlib (Python 3.9+) | Runs blocking subprocess without blocking bot event loop | Preferred over create_subprocess_exec for subprocess.run wrappers; avoids pipe-read blocking issue on some Linux kernels. |
| subprocess (stdlib) | stdlib | Invokes LibreOffice headless | subprocess.run with timeout=30; simpler than asyncio subprocess API for one-shot conversion. |
| pathlib.Path (stdlib) | stdlib | All file path construction | Avoids string path bugs; already used in config.py for TEMPLATES_DIR, CONTRACTS_DIR. |
| tempfile (stdlib) | stdlib | Temp DOCX before conversion | Named temp file in system temp dir; cleaned in finally block. |

### Already Installed — No Action Needed

| Package | Status |
|---------|--------|
| docxtpl==0.20.2 | Pinned in requirements.txt, not yet installed in dev env (Windows) — install before testing |
| SQLAlchemy==2.0.48 | Installed |
| aiosqlite==0.22.1 | Installed |

**Dev environment note:** `docxtpl`, `python-telegram-bot`, and `pydantic` are not installed in the local Windows Python environment. Run `pip install -r requirements.txt` before executing any Phase 3 code or tests.

---

## Architecture Patterns

### Module: `document_service.py`

Single-responsibility module. No Telegram imports. Consumes `ContractData`, produces a PDF file on disk.

```
rent-contract-bot/
├── document_service.py       # NEW — Phase 3
│   ├── generate_contract_number(data) -> str
│   ├── _build_context(data) -> dict
│   ├── _fill_template(template_path, context) -> Path   (sync, run via to_thread)
│   ├── _convert_to_pdf(docx_path, out_dir) -> Path      (sync, run via to_thread)
│   └── generate_contract(data: ContractData) -> str     # PUBLIC async entry point
├── storage/
│   └── templates/
│       ├── Г39/
│       │   └── contract_template.docx                   # NEW — Jinja2 {{ }} placeholders
│       └── Г38/
│           └── contract_template.docx                   # NEW — Jinja2 {{ }} placeholders
└── tests/
    └── test_document_service.py                         # NEW — Phase 3
```

### Pattern 1: ContractData → docxtpl Context Dict

`ContractData` fields must be converted to a flat context dict. Dates must be pre-formatted as strings because Jinja2's `strftime` filter is not available by default in docxtpl without a custom `jinja_env`.

```python
# Source: docxtpl.readthedocs.io — render() API
import datetime
from docxtpl import DocxTemplate
from models import ContractData

def _build_context(data: ContractData) -> dict:
    """Convert ContractData to a docxtpl-compatible context dict.

    All date fields pre-formatted as Russian ДД.ММ.ГГГГ strings.
    Decimal amounts formatted as integer strings (50000 not 50000.00).
    deposit_split drives the conditional section in the template.
    """
    deposit_half = data.deposit_amount / 2

    return {
        # Contract metadata
        "contract_number": data.contract_number,
        "contract_date": data.contract_date.strftime("%d.%m.%Y"),
        "act_date": data.act_date.strftime("%d.%m.%Y"),

        # Tenant personal
        "tenant_full_name": data.tenant_full_name,
        "tenant_dob": data.tenant_dob.strftime("%d.%m.%Y"),
        "tenant_birthplace": data.tenant_birthplace,
        "tenant_gender": data.tenant_gender,
        "tenant_address": data.tenant_address,

        # Passport
        "passport_series": data.passport_series,
        "passport_number": data.passport_number,
        "passport_issued_date": data.passport_issued_date.strftime("%d.%m.%Y"),
        "passport_issued_by": data.passport_issued_by,
        "passport_division_code": data.passport_division_code,

        # Contact
        "tenant_phone": data.tenant_phone,
        "tenant_email": data.tenant_email,

        # Financial
        "monthly_amount": int(data.monthly_amount),
        "deposit_amount": int(data.deposit_amount),
        "deposit_split": data.deposit_split,
        "deposit_half": int(deposit_half),
    }
```

### Pattern 2: Contract Number Generation (DOC-01)

Format: `{group}/{apartment}/{ДД.ММ.ГГГГ}` base, with sequence suffix on collision.

```python
# Source: PITFALLS.md Pitfall 9 — duplicate contract numbers
import datetime
from database import get_contract_by_number   # hypothetical lookup

def generate_contract_number(group: str, apartment: str, contract_date: datetime.date) -> str:
    """Generate unique contract number. Appends -2, -3 suffix on same-day collision."""
    base = f"{group}/{apartment}/{contract_date.strftime('%d.%m.%Y')}"
    candidate = base
    seq = 2
    # Check DB for collision — only needed in Phase 3 if DB lookup is in scope
    # For Phase 3 standalone test, uniqueness is by timestamp/seq only
    return candidate
```

**Note:** Full collision detection requires a DB read. For Phase 3, generate the base number and rely on the SQLite `UNIQUE` constraint on `contract_number` to surface duplicates at save time (Phase 6 integration). The sequence suffix can be added in Phase 6 when DB lookup is wired in. Document this deferral explicitly in the plan.

### Pattern 3: docxtpl Template Fill (DOC-02)

```python
# Source: docxtpl.readthedocs.io — DocxTemplate render + save
import tempfile
from pathlib import Path
from docxtpl import DocxTemplate

def _fill_template(template_path: Path, context: dict) -> Path:
    """Fill DOCX template. Returns path to filled temp DOCX file.

    Runs synchronously — call via asyncio.to_thread().
    Caller is responsible for deleting the returned temp file.
    """
    doc = DocxTemplate(str(template_path))
    doc.render(context)                           # autoescape=False (default) — correct for text

    # Write to named temp file in system temp dir
    with tempfile.NamedTemporaryFile(
        suffix=".docx", delete=False, prefix="contract_"
    ) as tmp:
        tmp_path = Path(tmp.name)

    doc.save(str(tmp_path))
    return tmp_path
```

### Pattern 4: LibreOffice Headless PDF Conversion (DOC-03)

```python
# Source: STACK.md + asyncio subprocess docs (docs.python.org/3/library/asyncio-subprocess.html)
import asyncio
import subprocess
from pathlib import Path

async def convert_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    """Convert filled DOCX to PDF via LibreOffice headless.

    Uses asyncio.to_thread so the bot event loop is not blocked.
    out_dir must exist before calling. docx_path must be absolute.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    result = await asyncio.to_thread(
        subprocess.run,
        [
            "libreoffice",
            "--headless",
            "--norestore",
            "--nofirststartwizard",
            "--convert-to", "pdf",
            "--outdir", str(out_dir),
            str(docx_path),
        ],
        capture_output=True,
        timeout=30,
    )

    expected_pdf = out_dir / (docx_path.stem + ".pdf")
    if not expected_pdf.exists():
        raise RuntimeError(
            f"LibreOffice conversion produced no output. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    return expected_pdf
```

### Pattern 5: Full generate_contract() with Cleanup

```python
# Combines Patterns 1-4 with guaranteed temp file cleanup
import asyncio
import logging
from pathlib import Path
from models import ContractData
import config

logger = logging.getLogger(__name__)

async def generate_contract(data: ContractData) -> str:
    """Fill template and convert to PDF. Returns absolute PDF path.

    Cleans up temp DOCX on success AND failure.
    Raises RuntimeError if conversion fails.
    """
    template_path = config.TEMPLATES_DIR / data.group / "contract_template.docx"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    context = _build_context(data)
    tmp_docx: Path | None = None

    try:
        tmp_docx = await asyncio.to_thread(_fill_template, template_path, context)
        out_dir = config.CONTRACTS_DIR / data.group / data.apartment
        pdf_path = await convert_to_pdf(tmp_docx, out_dir)
        logger.info("PDF generated: %s", pdf_path)
        return str(pdf_path)
    finally:
        if tmp_docx and tmp_docx.exists():
            tmp_docx.unlink()
            logger.debug("Cleaned up temp DOCX: %s", tmp_docx)
```

### Pattern 6: DOCX Template Jinja2 Syntax (for template authoring)

In the Word `.docx` template file, use these syntaxes:

```
Simple variable:        {{ tenant_full_name }}
Date (pre-formatted):   {{ contract_date }}
Conditional section:    {%p if deposit_split %}
                        Депозит вносится в два платежа: {{ deposit_half }} руб. + {{ deposit_half }} руб.
                        {%p endif %}
Non-split section:      {%p if not deposit_split %}
                        Депозит вносится единовременно: {{ deposit_amount }} руб.
                        {%p endif %}
```

**Key rule:** `{%p if ... %}` and `{%p endif %}` must be in their own paragraphs. The paragraph containing the tag is removed from output — only content between the tags appears. Do NOT mix `{%p %}` tags and content in the same paragraph.

### Anti-Patterns to Avoid

- **Using raw python-docx for template fill:** `paragraph.runs[i].text.replace()` silently fails when Word splits placeholders across XML runs (Pitfall 2). Never use this approach.
- **Calling subprocess.run() directly in an async handler:** Blocks the entire asyncio event loop for up to 30 seconds. Always wrap with `asyncio.to_thread()`.
- **Using relative paths with LibreOffice `--outdir`:** LibreOffice may write to working directory instead. Always use `str(absolute_path)`.
- **Not asserting PDF existence after conversion:** `subprocess.run` returns exit code 0 even when LibreOffice fails silently. Always assert `expected_pdf.exists()`.
- **Not formatting dates before adding to context:** Passing `datetime.date` objects to docxtpl and using `{{ date | strftime(...) }}` in templates requires a custom jinja_env. Pre-format all dates in `_build_context()` instead.
- **Placing temp DOCX cleanup inside the try block:** If conversion raises, cleanup is skipped. Always use `finally`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DOCX template variable substitution | Custom `str.replace()` loop over paragraphs/runs | `docxtpl` with `{{ }}` syntax | Word silently splits text into multiple XML runs; naive replace finds no match (Pitfall 2) |
| Conditional DOCX sections | XML manipulation to remove paragraphs | `{%p if condition %}` blocks in docxtpl | XML structure is complex; direct manipulation breaks styles and table structure |
| Async subprocess execution | Custom thread pool + Future wiring | `asyncio.to_thread(subprocess.run, ...)` | stdlib handles executor lifecycle; to_thread is cleaner than manual ThreadPoolExecutor for one-off calls |
| PDF output path construction | String manipulation of LibreOffice output | Assert `out_dir / (stem + ".pdf")` exists after call | LibreOffice always names PDF after the input file stem; constructing the expected path is deterministic |

**Key insight:** docxtpl is specifically built to solve the problem that makes every other DOCX-filling approach fragile on real Word documents.

---

## Common Pitfalls

### Pitfall A: Template Placeholder Syntax Mismatch (HIGH RISK for this phase)

**What goes wrong:** Templates created/edited in Word with `[PLACEHOLDER]` bracket syntax cannot be filled by docxtpl. docxtpl only processes `{{ }}` Jinja2 delimiters.

**Why it happens:** The original spec used bracket syntax; docxtpl requires Jinja2 syntax. The project blockers list (STATE.md) flags this explicitly.

**How to avoid:** Create templates from scratch with `{{ field_name }}` syntax. The `storage/templates/Г39/` and `storage/templates/Г38/` directories are currently empty — no migration needed, but the template authoring task in Wave 1 must use Jinja2 syntax.

**Warning signs:** docxtpl renders without error but the output DOCX still contains literal `{{ field_name }}` text → the placeholder is split across XML runs. Verify by calling `doc.get_undeclared_template_variables({})` before render.

### Pitfall B: LibreOffice Not Available in Dev Environment

**What goes wrong:** Tests that invoke LibreOffice subprocess fail on the developer's Windows machine (LibreOffice not in PATH). CI would also fail if LibreOffice is not installed.

**How to avoid:** Tests for the PDF conversion step must be skipped or mocked when LibreOffice is not available. Use `pytest.importorskip` or a fixture that skips if `shutil.which("libreoffice") is None`. Integration test (full DOCX→PDF) belongs in a separate test class marked `@pytest.mark.integration`.

**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'libreoffice'` during test run on Windows dev machine.

### Pitfall C: Font Substitution Breaks PDF Layout (HIGH RISK for Ubuntu deployment)

**What goes wrong:** Ubuntu servers lack Microsoft fonts (Calibri, Cambria). LibreOffice substitutes metrically-incompatible fonts, causing text overflow, shifted line breaks, and broken table cells in the PDF.

**How to avoid:** Install `fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation` on the server before the first PDF generation test. This is a one-time server setup step.

**Warning signs:** `fc-list | grep -i calibri` returns empty on the server. Generated PDF has text cut off at table cell boundaries.

### Pitfall D: LibreOffice Lock File from Previous Crash (MODERATE RISK)

**What goes wrong:** A crashed LibreOffice process leaves a lock file in `/tmp/`. The next headless invocation hangs waiting for the lock.

**How to avoid:** Pass `--norestore` and `--nofirststartwizard` flags (shown in Pattern 4 above). Add 30-second timeout. In error handler, log a note to check `ls /tmp/.~lock.*`.

**Warning signs:** LibreOffice conversion hangs indefinitely; `ps aux | grep soffice` shows zombie process.

### Pitfall E: LibreOffice Outputs PDF to Wrong Directory

**What goes wrong:** When `--outdir` is a relative path or the path does not exist, LibreOffice writes the PDF to its working directory (not where the bot looks).

**How to avoid:** Always call `out_dir.mkdir(parents=True, exist_ok=True)` before the subprocess call. Always pass `str(absolute_path)` for both `--outdir` and the input DOCX. Assert `expected_pdf.exists()` after the call.

### Pitfall F: Decimal Amounts in Context Cause docxtpl Rendering Issues

**What goes wrong:** Passing `Decimal("50000.00")` to the template context and rendering `{{ monthly_amount }}` produces `50000.00` in the document (with decimal point), which looks wrong for whole-number rent amounts.

**How to avoid:** Convert Decimals to `int` (or a locale-formatted string) in `_build_context()` before passing to docxtpl. See Pattern 1.

---

## Runtime State Inventory

> This is a greenfield document generation phase. No rename/refactor in scope. Skipped.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All code | Yes | 3.12.10 | — |
| docxtpl 0.20.2 | DOC-02 | Not installed (dev) | — | Install via requirements.txt |
| LibreOffice headless | DOC-03 | Not in PATH (dev) | — | Skip/mock in unit tests; required on Ubuntu prod |
| SQLAlchemy / aiosqlite | Context only | Yes (installed) | 2.0.48 / 0.22.1 | — |
| pytest + pytest-asyncio | Tests | Yes (35 tests passing) | — | — |

**Missing dependencies with no fallback:**
- `LibreOffice` on Ubuntu production server — must be installed (`sudo apt-get install -y libreoffice`) before Phase 3 success criteria 3 can be verified.
- `fonts-crosextra-carlito`, `fonts-crosextra-caladea`, `fonts-liberation` on Ubuntu server — required for Pitfall C avoidance.

**Missing dependencies with fallback (dev):**
- `LibreOffice` on dev Windows machine — unit tests for `_fill_template()` and `_build_context()` do NOT require LibreOffice. PDF conversion tests use `@pytest.mark.skipif(shutil.which("libreoffice") is None, ...)`.
- `docxtpl` not installed in dev env — run `pip install docxtpl==0.20.2` or full `pip install -r requirements.txt`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| Quick run command | `python -m pytest tests/test_document_service.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOC-01 | Contract number format `Г39/42/15.03.2024` | unit | `pytest tests/test_document_service.py::test_contract_number_format -x` | ❌ Wave 0 |
| DOC-01 | Contract number changes if same base already used | unit | `pytest tests/test_document_service.py::test_contract_number_uniqueness -x` | ❌ Wave 0 |
| DOC-02 | All `{{ }}` placeholders replaced in output DOCX | unit | `pytest tests/test_document_service.py::test_fill_template_replaces_all_placeholders -x` | ❌ Wave 0 |
| DOC-02 | deposit_split=True renders split-payment section | unit | `pytest tests/test_document_service.py::test_fill_template_deposit_split_section -x` | ❌ Wave 0 |
| DOC-02 | deposit_split=False renders lump-sum section | unit | `pytest tests/test_document_service.py::test_fill_template_lump_sum_section -x` | ❌ Wave 0 |
| DOC-03 | PDF file exists after conversion | integration (skip if no LO) | `pytest tests/test_document_service.py::test_pdf_conversion -x -m integration` | ❌ Wave 0 |
| DOC-03 | Temp DOCX is deleted after successful conversion | unit/integration | `pytest tests/test_document_service.py::test_temp_docx_cleaned_up_on_success -x` | ❌ Wave 0 |
| DOC-03 | Temp DOCX is deleted even if conversion raises | unit | `pytest tests/test_document_service.py::test_temp_docx_cleaned_up_on_failure -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_document_service.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green (all 35 existing + new document service tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_document_service.py` — covers DOC-01, DOC-02, DOC-03 (all 8 tests above)
- [ ] `tests/fixtures/contract_template_test.docx` — minimal Jinja2 template used only by tests (avoids dependency on real templates)
- [ ] `document_service.py` — the module under test

*(Existing `tests/__init__.py`, `pyproject.toml` pytest config, and pytest-asyncio are already present — no framework setup needed.)*

---

## Code Examples

### Verified: DocxTemplate render with context dict

```python
# Source: https://docxtpl.readthedocs.io/en/latest/
from docxtpl import DocxTemplate

doc = DocxTemplate("template.docx")
context = {
    "tenant_full_name": "Иванов Иван Иванович",
    "contract_date": "15.03.2024",
    "deposit_split": True,
    "deposit_half": 50000,
}
doc.render(context)           # autoescape=False (default) — correct for plain text fields
doc.save("filled.docx")
```

### Verified: Paragraph-level conditional block in DOCX template

```
# In Word .docx template (place each {%p %} tag in its own paragraph):

{%p if deposit_split %}
Депозит в размере {{ deposit_amount }} руб. вносится двумя платежами по {{ deposit_half }} руб.
{%p endif %}
{%p if not deposit_split %}
Депозит в размере {{ deposit_amount }} руб. вносится единовременно.
{%p endif %}
```

### Verified: asyncio.to_thread wrapping subprocess.run

```python
# Source: https://docs.python.org/3/library/asyncio-subprocess.html
# Source: Python asyncio docs — asyncio.to_thread() for blocking calls
import asyncio
import subprocess

result = await asyncio.to_thread(
    subprocess.run,
    ["libreoffice", "--headless", "--norestore", "--nofirststartwizard",
     "--convert-to", "pdf", "--outdir", "/absolute/out/dir", "/absolute/input.docx"],
    capture_output=True,
    timeout=30,
)
# LibreOffice names output as input_stem.pdf
```

### Verified: Skip test when LibreOffice not available

```python
import shutil
import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("libreoffice") is None,
    reason="LibreOffice not installed"
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `subprocess.run()` directly in async handler | `asyncio.to_thread(subprocess.run, ...)` | Python 3.9 (to_thread added) | Event loop not blocked during 5-30s conversion |
| `[PLACEHOLDER]` bracket syntax with python-docx | `{{ placeholder }}` Jinja2 via docxtpl | 2016+ (docxtpl library) | Run-splitting is handled automatically; no XML surgery |
| `unoconv` daemon | Direct `libreoffice --headless` call | N/A (project decision) | Eliminates server daemon; simpler process management |
| `subprocess.run(..., timeout=30)` with process hanging | `asyncio.wait_for(proc.communicate(), timeout=30)` if using create_subprocess_exec | N/A | For asyncio subprocess API; to_thread pattern uses subprocess timeout param directly |

**Deprecated/outdated patterns:**
- `unoconv`: Adds daemon complexity, project explicitly chose direct LibreOffice invocation (STACK.md).
- Raw `python-docx` template filling: Cannot handle run-split placeholders. STACK.md explicitly lists it as "What NOT to Use."

---

## Open Questions

1. **Template file per apartment or one template per group?**
   - What we know: `config.py` defines `TEMPLATES_DIR / group` (e.g., `storage/templates/Г39/`). There is no apartment-level subdirectory in config.
   - What's unclear: Does each apartment have different contract terms (parking, floor, size) that require a separate template, or is one template per group sufficient with fields covering all variables?
   - Recommendation: Implement `document_service.py` to look up `TEMPLATES_DIR / group / "contract_template.docx"`. If per-apartment templates are needed later, add `TEMPLATES_DIR / group / apartment / "contract_template.docx"` as a fallback chain. Decide at template authoring time (Wave 1 of plans).

2. **Collision detection for DOC-01 uniqueness — Phase 3 or Phase 6?**
   - What we know: Pitfall 9 documents the same-day collision risk. Full fix requires a DB lookup. DB layer exists (Phase 2 complete) but `generate_contract()` in Phase 3 has no mandate to save to DB (that's Phase 6 integration).
   - What's unclear: Should Phase 3 include a DB check, or just generate the base number and let Phase 6 handle collision on save (unique constraint will raise)?
   - Recommendation: Phase 3 generates the base number only. Add a comment in code marking where the collision-check loop should go in Phase 6. This keeps Phase 3 Telegram-free and DB-free.

3. **PDF naming convention — contract number or UUID?**
   - What we know: Contract number contains slashes (`Г39/42/15.03.2024`) which are not valid in filenames.
   - What's unclear: How should the PDF filename be constructed from the contract number?
   - Recommendation: Sanitize by replacing `/` with `_`: `Г39_42_15.03.2024.pdf`. Store the original slash-formatted number in the DB `contract_number` column; use the sanitized form only for filesystem paths.

---

## Project Constraints (from CLAUDE.md)

The following directives are drawn from `CLAUDE.md` and must be honored:

| Directive | Source | Impact on Phase 3 |
|-----------|--------|-------------------|
| Tech stack: Python 3.10+, python-telegram-bot 20.x (async), docxtpl | CLAUDE.md Constraints | document_service.py must be async-compatible; use docxtpl not python-docx directly |
| PDF conversion: LibreOffice headless (must be installed on server) | CLAUDE.md Constraints | No alternative PDF engine; Ubuntu server prerequisite must be in plan |
| GSD workflow: make changes through GSD entry points only | CLAUDE.md GSD Workflow Enforcement | All file edits flow through /gsd:execute-phase |
| Pinned deps with == (no ranges) | STATE.md Phase 01 decision | If any new dep is added to requirements.txt it must be pinned with == |
| config.validate() inside main() not at module import | STATE.md Phase 01 decision | document_service.py imports config module directly — this is safe as long as validate() is not called |
| Result-style returns (value | str) instead of exceptions at FSM layer | STATE.md Phase 02 decision | This pattern is for the FSM/validator layer. document_service.py (pure service, no FSM) should raise exceptions; the FSM layer (Phase 5) catches and converts to error strings |
| stdlib only for Phase 2 validators | STATE.md Phase 02 decision | Does NOT apply to Phase 3; docxtpl is an approved library for this phase |

---

## Sources

### Primary (HIGH confidence)
- [docxtpl.readthedocs.io](https://docxtpl.readthedocs.io/en/latest/) — render() signature, {%p %} paragraph conditional syntax, RichText API, get_undeclared_template_variables()
- [docs.python.org/3/library/asyncio-subprocess.html](https://docs.python.org/3/library/asyncio-subprocess.html) — asyncio subprocess API, asyncio.to_thread() pattern
- `models.py` (project) — ContractData field names and types, verified directly
- `config.py` (project) — TEMPLATES_DIR, CONTRACTS_DIR paths, verified directly
- `.planning/research/STACK.md` (project) — docxtpl 0.20.2, LibreOffice headless invocation pattern, HIGH confidence from PyPI verification
- `.planning/research/PITFALLS.md` (project) — Pitfall 2 (run splitting), Pitfall 3 (font substitution), Pitfall 6 (zombie processes), Pitfall 9 (duplicate numbers), Pitfall 12 (outdir confusion)

### Secondary (MEDIUM confidence)
- [mlhive.com docxtpl guide 2025](https://mlhive.com/2025/12/mastering-dynamic-word-document-generation-python-docxtpl) — docxtpl usage patterns, cross-verified with official docs
- [STACK.md WebSearch: LibreOffice headless subprocess 2025](https://tariknazorek.medium.com/convert-office-files-to-pdf-with-libreoffice-and-python-a70052121c44) — subprocess invocation pattern

### Tertiary (LOW confidence — flagged)
- WebSearch finding: `asyncio.to_thread()` preferred over `create_subprocess_exec` for one-shot subprocess.run wrappers — verified by Python docs logic but not by a single authoritative benchmark source. The functional result (non-blocking event loop) is HIGH confidence; the preference framing is MEDIUM.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified in requirements.txt and PyPI
- Architecture: HIGH — docxtpl API verified from official docs; asyncio pattern from Python stdlib docs
- Pitfalls: HIGH — sourced from project-specific PITFALLS.md plus official docs cross-verification
- Template syntax: HIGH — verified from docxtpl.readthedocs.io directly
- LibreOffice availability: HIGH — confirmed not in dev PATH; known server requirement

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days; stable libraries)
