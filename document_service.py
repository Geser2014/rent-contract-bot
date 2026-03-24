"""Document generation service.

Public API:
    generate_contract_number(group, apartment, contract_date) -> str
    generate_contract(data: ContractData) -> str   [async, returns PDF path]

Internal helpers (not part of public API, but directly tested):
    _build_context(data) -> dict
    _fill_template(template_path, context) -> Path
"""
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

import config
from models import ContractData

logger = logging.getLogger(__name__)


def generate_contract_number(group: str, apartment: str, contract_date) -> str:
    """Generate contract number in format group/apartment/DD.MM.YYYY.

    Example: "Г39/42/15.03.2024"

    NOTE: Same-day collision detection (suffix -2, -3, ...) is deferred to
    Phase 6 when the DB lookup is wired in. The SQLite UNIQUE constraint on
    contract_number will surface duplicates at save time until then.
    """
    return f"{group}/{apartment}/{contract_date.strftime('%d.%m.%Y')}"


def _build_context(data: ContractData) -> dict:
    """Convert ContractData to a docxtpl-compatible context dict.

    All date fields are pre-formatted as ДД.ММ.ГГГГ strings.
    Decimal amounts are converted to int (no trailing .00).
    deposit_half drives the conditional split-payment section in the template.
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

        # Financial — Decimal → int to avoid "50000.00" in document
        "monthly_amount": int(data.monthly_amount),
        "deposit_amount": int(data.deposit_amount),
        "deposit_split": data.deposit_split,
        "deposit_half": int(deposit_half),
    }


def _fill_template(template_path: Path, context: dict) -> Path:
    """Fill DOCX template and return path to a filled temp DOCX file.

    Runs synchronously — caller must wrap with asyncio.to_thread().
    Caller is responsible for deleting the returned temp file.

    Raises FileNotFoundError if template_path does not exist.
    """
    from docxtpl import DocxTemplate  # deferred: docxtpl not always installed in dev env

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    doc = DocxTemplate(str(template_path))
    doc.render(context)  # autoescape=False (default) — correct for plain text fields

    with tempfile.NamedTemporaryFile(
        suffix=".docx", delete=False, prefix="contract_"
    ) as tmp:
        tmp_path = Path(tmp.name)

    doc.save(str(tmp_path))
    return tmp_path


def _convert_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    """Convert filled DOCX to PDF via LibreOffice headless.

    Runs synchronously — caller must wrap with asyncio.to_thread().
    out_dir must exist before calling. docx_path must be absolute.

    Raises RuntimeError if LibreOffice produces no output.
    Raises subprocess.TimeoutExpired if conversion exceeds 30 seconds.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--norestore",
            "--nofirststartwizard",
            "--convert-to", "pdf",
            "--outdir", str(out_dir.resolve()),
            str(docx_path.resolve()),
        ],
        capture_output=True,
        timeout=30,
    )

    expected_pdf = out_dir / (docx_path.stem + ".pdf")
    if not expected_pdf.exists():
        raise RuntimeError(
            f"LibreOffice conversion produced no output. "
            f"returncode={result.returncode} "
            f"stdout={result.stdout.decode('utf-8', errors='replace')!r} "
            f"stderr={result.stderr.decode('utf-8', errors='replace')!r}"
        )

    return expected_pdf


async def generate_contract(data: ContractData) -> str:
    """Fill template and convert to PDF. Returns absolute PDF path as string.

    Cleans up temp DOCX on both success AND failure (finally block).
    Raises FileNotFoundError if template is missing.
    Raises RuntimeError if LibreOffice conversion fails.
    """
    template_path = config.TEMPLATES_DIR / data.group / "contract_template.docx"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    context = _build_context(data)

    # Sanitize contract number for filesystem: "Г39/42/15.03.2024" → "Г39_42_15.03.2024"
    safe_name = data.contract_number.replace("/", "_")
    out_dir = config.CONTRACTS_DIR / data.group / data.apartment

    tmp_docx: Path | None = None
    try:
        tmp_docx = await asyncio.to_thread(_fill_template, template_path, context)

        # Rename temp file to use contract number stem for a predictable PDF name
        named_docx = tmp_docx.parent / f"{safe_name}.docx"
        tmp_docx.rename(named_docx)
        tmp_docx = named_docx

        pdf_path = await asyncio.to_thread(_convert_to_pdf, tmp_docx, out_dir)
        logger.info("PDF generated: %s", pdf_path)
        return str(pdf_path)
    finally:
        if tmp_docx and tmp_docx.exists():
            tmp_docx.unlink()
            logger.debug("Cleaned up temp DOCX: %s", tmp_docx)
