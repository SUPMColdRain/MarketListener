"""FULL-701 fixed samples: HTML/Excel/PDF/announcement import and locations."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from market_monitor.industry_graph.importers import (
    GraphImportError,
    GraphImporter,
    ImportedRecord,
    PARSED_VERSION,
)


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "graph"


def _importer() -> GraphImporter:
    return GraphImporter(now=__import__("datetime").datetime(2026, 8, 6, 1, 0, 0))


def test_html_import_records_dom_location_and_sha256() -> None:
    path = FIXTURES / "html" / "supply-chain.html"
    result = _importer().import_file(path)

    assert result.source_type == "HTML"
    assert result.parsed_version == PARSED_VERSION
    assert result.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not result.duplicate
    assert result.records
    assert any(record.location.dom and "table" in record.location.dom for record in result.records)
    assert any("贵州茅台" in record.snippet for record in result.records)


def test_excel_import_records_cell_location() -> None:
    path = FIXTURES / "excel" / "supply-chain.xlsx"
    result = _importer().import_file(path)

    assert result.source_type == "EXCEL"
    assert result.records
    assert any(record.location.cell and record.location.cell.startswith("Sheet1!") for record in result.records)
    assert any("碳酸锂" in record.snippet for record in result.records)


def test_pdf_import_records_page_and_line() -> None:
    path = FIXTURES / "pdf" / "supply-chain.pdf"
    result = _importer().import_file(path)

    assert result.source_type == "PDF"
    assert result.records
    assert all(record.location.page is not None and record.location.line is not None for record in result.records)
    assert any("supplies" in record.snippet.lower() or "produces" in record.snippet.lower() for record in result.records)


def test_announcement_import_records_line_and_offset() -> None:
    path = FIXTURES / "announcement" / "2026-08-01-moutai.txt"
    result = _importer().import_file(path)

    assert result.source_type == "ANNOUNCEMENT"
    assert result.records
    assert all(record.location.line is not None for record in result.records)
    assert any("华致酒行" in record.snippet for record in result.records)


def test_duplicate_import_is_idempotent() -> None:
    path = FIXTURES / "html" / "supply-chain.html"
    importer = _importer()
    first = importer.import_file(path)
    second = importer.import_file(path)

    assert not first.duplicate
    assert second.duplicate
    assert second.records == ()
    assert second.sha256 == first.sha256


def test_mismatched_source_type_is_classified(tmp_path) -> None:
    text = tmp_path / "announcement.txt"
    text.write_bytes("贵州茅台向华致酒行供应茅台酒。\n".encode("utf-8"))

    with pytest.raises(GraphImportError) as error:
        _importer().import_file(text, source_type="PDF")

    assert error.value.category == "CORRUPT_FILE"


def test_corrupt_pdf_is_classified(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"this is not a pdf at all")

    with pytest.raises(GraphImportError) as error:
        _importer().import_file(corrupt)

    assert error.value.category == "CORRUPT_FILE"


def test_unknown_suffix_is_rejected(tmp_path) -> None:
    unknown = tmp_path / "source.docx"
    unknown.write_bytes(b"ignored")

    with pytest.raises(GraphImportError) as error:
        _importer().import_file(unknown)

    assert error.value.category == "UNSUPPORTED_FORMAT"


def test_records_can_become_schema_valid_evidence() -> None:
    record: ImportedRecord = _importer().import_file(FIXTURES / "pdf" / "supply-chain.pdf").records[0]
    evidence = record.to_evidence("evidence.0001")

    assert evidence["schema_version"] == 1
    assert evidence["evidence_id"] == "evidence.0001"
    assert evidence["location"] == record.location.as_mapping()
    assert evidence["parsed_version"] == PARSED_VERSION
