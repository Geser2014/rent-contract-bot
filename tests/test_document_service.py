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
