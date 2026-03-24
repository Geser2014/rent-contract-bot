"""Tests for document_service.py — DOC-01 and DOC-02.

Run: python -m pytest tests/test_document_service.py -x -q
All PDF/LibreOffice tests are in a separate integration class (skipped on Windows dev).
"""
import datetime
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from docx import Document

# Adjust sys.path so tests can import project modules when run from project root.
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import document_service
from document_service import _build_context, _fill_template, generate_contract_number
from models import ContractData

FIXTURE_TEMPLATE = Path(__file__).parent / "fixtures" / "contract_template_test.docx"


def make_contract_data(deposit_split: bool = False) -> ContractData:
    """Return a fully-populated ContractData fixture."""
    return ContractData(
        contract_number="Г39/42/15.03.2024",
        group="Г39",
        apartment="42",
        tenant_full_name="Иванов Иван Иванович",
        tenant_dob=datetime.date(1990, 5, 20),
        tenant_birthplace="г. Москва",
        tenant_gender="М",
        tenant_address="г. Москва, ул. Ленина, д. 1, кв. 1",
        passport_series="1234",
        passport_number="567890",
        passport_issued_date=datetime.date(2010, 6, 15),
        passport_issued_by="МВД России по г. Москве",
        passport_division_code="770-001",
        tenant_phone="+79161234567",
        tenant_email="ivan@example.com",
        contract_date=datetime.date(2024, 3, 15),
        act_date=datetime.date(2024, 3, 20),
        monthly_amount=Decimal("50000"),
        deposit_amount=Decimal("100000"),
        deposit_split=deposit_split,
    )


class TestContractNumber:
    def test_contract_number_format(self):
        result = generate_contract_number("Г39", "42", datetime.date(2024, 3, 15))
        assert result == "Г39/42/15.03.2024"

    def test_contract_number_format_g38(self):
        result = generate_contract_number("Г38", "7", datetime.date(2024, 12, 1))
        assert result == "Г38/7/01.12.2024"


class TestFillTemplate:
    def _get_paragraphs(self, docx_path: Path) -> list[str]:
        """Return all non-empty paragraph texts from a DOCX file."""
        doc = Document(str(docx_path))
        return [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    def test_fill_template_replaces_all_placeholders(self):
        data = make_contract_data()
        context = _build_context(data)
        tmp = _fill_template(FIXTURE_TEMPLATE, context)
        try:
            paragraphs = self._get_paragraphs(tmp)
            combined = "\n".join(paragraphs)
            assert "{{" not in combined, f"Unreplaced placeholder found: {combined[:200]}"
            assert "}}" not in combined, f"Unreplaced placeholder found: {combined[:200]}"
        finally:
            tmp.unlink(missing_ok=True)

    def test_fill_template_deposit_split_section(self):
        data = make_contract_data(deposit_split=True)
        context = _build_context(data)
        tmp = _fill_template(FIXTURE_TEMPLATE, context)
        try:
            paragraphs = self._get_paragraphs(tmp)
            combined = "\n".join(paragraphs)
            assert "SPLIT:" in combined, "Split-payment paragraph missing when deposit_split=True"
            assert "LUMP:" not in combined, "Lump-sum paragraph present when deposit_split=True"
        finally:
            tmp.unlink(missing_ok=True)

    def test_fill_template_lump_sum_section(self):
        data = make_contract_data(deposit_split=False)
        context = _build_context(data)
        tmp = _fill_template(FIXTURE_TEMPLATE, context)
        try:
            paragraphs = self._get_paragraphs(tmp)
            combined = "\n".join(paragraphs)
            assert "LUMP:" in combined, "Lump-sum paragraph missing when deposit_split=False"
            assert "SPLIT:" not in combined, "Split paragraph present when deposit_split=False"
        finally:
            tmp.unlink(missing_ok=True)


class TestPdfConversion:
    """DOC-03: LibreOffice conversion + temp file cleanup."""

    def test_convert_to_pdf_raises_when_no_output(self, tmp_path):
        """_convert_to_pdf raises RuntimeError when LibreOffice exits 0 but produces no PDF."""
        import document_service
        from unittest.mock import patch, MagicMock

        # Create a dummy DOCX input so the path exists
        dummy_docx = tmp_path / "contract_dummy.docx"
        dummy_docx.write_bytes(b"dummy")

        # Mock subprocess.run — exit code 0 but we do NOT create the expected PDF
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""

        with patch("document_service.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="no output"):
                document_service._convert_to_pdf(dummy_docx, tmp_path)

    def test_generate_contract_cleanup_on_failure(self, tmp_path):
        """generate_contract deletes temp DOCX even when _convert_to_pdf raises."""
        import asyncio
        import document_service
        from unittest.mock import patch

        # Create a real temp file that _fill_template "returns"
        sentinel_file = tmp_path / "contract_sentinel.docx"
        sentinel_file.write_bytes(b"sentinel")

        data = make_contract_data()

        def fake_fill(template_path, context):
            # Return a renamed copy of sentinel so generate_contract can rename it
            return sentinel_file

        with patch.object(document_service, "_fill_template", side_effect=fake_fill):
            with patch.object(
                document_service,
                "_convert_to_pdf",
                side_effect=RuntimeError("conversion failed"),
            ):
                with pytest.raises(RuntimeError, match="conversion failed"):
                    asyncio.run(document_service.generate_contract(data))

        # The renamed temp file must be cleaned up by the finally block
        safe_name = data.contract_number.replace("/", "_")
        renamed = sentinel_file.parent / f"{safe_name}.docx"
        assert not renamed.exists(), "Temp DOCX not cleaned up after failure"

    @pytest.mark.skipif(
        shutil.which("libreoffice") is None,
        reason="LibreOffice not installed — skipped on dev machine",
    )
    @pytest.mark.integration
    def test_pdf_conversion_integration(self, tmp_path):
        """Full generate_contract() pipeline: template fill -> LibreOffice PDF -> cleanup."""
        import asyncio
        import document_service

        # Point config paths to tmp_path so we don't pollute storage/
        import config as cfg
        original_contracts_dir = cfg.CONTRACTS_DIR
        cfg.CONTRACTS_DIR = tmp_path / "contracts"
        cfg.CONTRACTS_DIR.mkdir(parents=True)

        try:
            data = make_contract_data()
            pdf_path_str = asyncio.run(document_service.generate_contract(data))
            pdf_path = Path(pdf_path_str)

            assert pdf_path.exists(), f"PDF not produced: {pdf_path}"
            assert pdf_path.suffix == ".pdf"
            assert pdf_path.stat().st_size > 1024, "PDF is suspiciously small (<1 KB)"

            # Temp DOCX must be gone
            safe_name = data.contract_number.replace("/", "_")
            tmp_docx = Path(tempfile.gettempdir()) / f"{safe_name}.docx"
            assert not tmp_docx.exists(), "Temp DOCX was not cleaned up"
        finally:
            cfg.CONTRACTS_DIR = original_contracts_dir
