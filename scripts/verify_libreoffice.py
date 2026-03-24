#!/usr/bin/env python3
"""Verify LibreOffice headless installation and font availability.

Run: python scripts/verify_libreoffice.py

Exit codes:
  0 — LibreOffice installed and PDF produced (fonts may have warnings)
  1 — LibreOffice not found or conversion failed
"""
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_test_docx(output_path: Path) -> None:
    """Create a minimal DOCX for conversion testing."""
    from docx import Document  # python-docx (transitive dep of docxtpl)

    doc = Document()
    doc.add_paragraph("LibreOffice font verification test.")
    doc.add_paragraph("Тест шрифтов LibreOffice. Договор аренды.")
    doc.add_paragraph("Calibri Cambria Times New Roman Arial")
    doc.save(str(output_path))


def verify_libreoffice() -> bool:
    """Run conversion and return True if PDF was produced."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docx_path = tmp / "libreoffice_test.docx"
        expected_pdf = tmp / "libreoffice_test.pdf"

        print("Creating test DOCX...")
        try:
            create_test_docx(docx_path)
        except Exception as e:
            print(f"FAIL: Could not create test DOCX: {e}", file=sys.stderr)
            return False

        print("Running LibreOffice headless conversion...")
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--norestore",
                "--nofirststartwizard",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(docx_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"FAIL: LibreOffice exited with code {result.returncode}", file=sys.stderr)
            print(f"stderr: {result.stderr}", file=sys.stderr)
            return False

        # Check for font substitution warnings
        combined_output = result.stdout + result.stderr
        font_warning_keywords = ["substitut", "FontName", "font replacement", "cannot open"]
        warnings_found = [kw for kw in font_warning_keywords if kw.lower() in combined_output.lower()]
        if warnings_found:
            print("WARNING: Font substitution indicators found in LibreOffice output:")
            for line in combined_output.splitlines():
                if any(kw.lower() in line.lower() for kw in font_warning_keywords):
                    print(f"  {line}")
            print(
                "\nRecommended fix:\n"
                "  sudo apt-get install fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation\n"
                "Then re-run this script."
            )

        if not expected_pdf.exists():
            print(f"FAIL: PDF not produced at expected path: {expected_pdf}", file=sys.stderr)
            return False

        pdf_size = expected_pdf.stat().st_size
        if pdf_size < 1000:
            print(f"FAIL: PDF file too small ({pdf_size} bytes) — likely empty", file=sys.stderr)
            return False

        print(f"PASS: PDF produced ({pdf_size} bytes)")
        if not warnings_found:
            print("PASS: No font substitution warnings detected")
        return True


if __name__ == "__main__":
    success = verify_libreoffice()
    sys.exit(0 if success else 1)
