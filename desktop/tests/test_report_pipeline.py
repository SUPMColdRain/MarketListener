"""产业链研报知识库流水线：聚合、核验与 SVG 图谱生成的轻量回归测试。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from market_monitor.report_pipeline import (
    _process_one,
    build_chain_index,
    verify_report_batch,
)


def _write_report(
    output_root: Path,
    report_id: str,
    *,
    primary_chain: str,
    related_chains: list[str],
    facts: list[dict[str, object]],
    warnings: list[str] | None = None,
) -> Path:
    document = {
        "schema_version": 1,
        "report_id": report_id,
        "file_name": f"{report_id}.pdf",
        "title": f"{report_id} 行业深度报告",
        "status": "REVIEWED",
        "processed_at": "2026-08-09T00:00:00+08:00",
        "primary_chain": primary_chain,
        "related_chains": related_chains,
        "facts": facts,
        "cooccurrences": [],
        "warnings": warnings or [],
    }
    path = output_root / f"report_{report_id}.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _fact(
    entity: str,
    entity_type: str,
    chain: str,
    *,
    evidence: str = "报告第 3 页明确提到该企业与产品关系。",
) -> dict[str, object]:
    return {
        "entity": entity,
        "entity_type": entity_type,
        "chain": chain,
        "stage": "中游",
        "evidence": evidence,
        "page": 3,
        "confidence": 0.9,
    }


def test_build_chain_index_aggregates_facts_and_writes_artifacts(tmp_path: Path) -> None:
    output_root = tmp_path / "industry"
    output_root.mkdir()
    _write_report(
        output_root,
        "a1b2",
        primary_chain="锂电池",
        related_chains=[],
        facts=[
            _fact("宁德时代", "COMPANY", "锂电池"),
            _fact("磷酸铁锂", "PRODUCT", "锂电池"),
        ],
    )
    _write_report(
        output_root,
        "c3d4",
        primary_chain="光伏",
        related_chains=["锂电池"],
        facts=[_fact("碳酸锂", "RAW_MATERIAL", "锂电池")],
    )

    index = build_chain_index(output_root)

    assert index["chain_count"] == 2
    assert index["report_count"] == 2
    assert index["fact_count"] == 3
    by_name = {item["chain"]: item for item in index["chains"]}
    assert by_name["锂电池"]["report_count"] == 2
    assert by_name["锂电池"]["fact_count"] == 3
    assert by_name["光伏"]["report_count"] == 1
    assert (output_root / "chain_index.json").is_file()
    assert not (output_root / "industry-map.html").exists()


def test_build_chain_index_includes_per_fact_chains_outside_declared(tmp_path: Path) -> None:
    output_root = tmp_path / "industry"
    output_root.mkdir()
    _write_report(
        output_root,
        "a1b3",
        primary_chain="锂电池",
        related_chains=[],
        facts=[
            _fact("宁德时代", "COMPANY", "锂电池"),
            _fact("英伟达", "COMPANY", "算力芯片"),
        ],
    )

    index = build_chain_index(output_root)

    assert index["chain_count"] == 2
    assert index["fact_count"] == 2
    by_name = {item["chain"]: item for item in index["chains"]}
    assert by_name["锂电池"]["fact_count"] == 1
    assert by_name["算力芯片"]["fact_count"] == 1
    assert by_name["算力芯片"]["report_count"] == 1
    assert by_name["算力芯片"]["reports"][0]["primary"] is False
    assert any(fact["entity"] == "英伟达" for fact in by_name["算力芯片"]["facts"])



def test_verify_report_batch_flags_empty_or_warning_heavy_report(tmp_path: Path) -> None:
    output_root = tmp_path / "industry"
    output_root.mkdir()
    good = _write_report(
        output_root,
        "good1",
        primary_chain="锂电池",
        related_chains=[],
        facts=[_fact("宁德时代", "COMPANY", "锂电池")],
        warnings=["字体嵌入异常"],
    )
    bad = _write_report(
        output_root,
        "bad01",
        primary_chain="锂电池",
        related_chains=[],
        facts=[],
        warnings=["警告一", "警告二", "警告三", "警告四", "警告五"],
    )

    summary = verify_report_batch(output_root, workers=2)

    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["flagged"] == 1
    assert summary["failed"] == 0
    assert (output_root / "review_summary.json").is_file()

    good_doc = json.loads(good.read_text(encoding="utf-8"))
    assert good_doc["review"]["passed"] is True
    bad_doc = json.loads(bad.read_text(encoding="utf-8"))
    assert bad_doc["review"]["passed"] is False
    assert any("未抽取到任何事实" in issue for issue in bad_doc["review"]["issues"])


class _FakePage:
    """最小化 pypdf 页面对象，供 _process_one 单测使用。"""

    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


def _fake_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "fake-report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return pdf


def _patch_pipeline_pdf_and_whitelist(monkeypatch, page_text: str):
    """把 PdfReader 与白名单替换为可预测的假实现，避免依赖真实 PDF 与 silver 数据。"""

    import market_monitor.report_pipeline as pipeline

    class _FakeReader:
        def __init__(self, path: str) -> None:
            self.pages = [_FakePage(page_text)]

    monkeypatch.setattr(pipeline, "PdfReader", _FakeReader)
    monkeypatch.setattr(
        pipeline,
        "_load_whitelist",
        lambda: ({"宁德时代"}, {"锂电池"}, {"碳酸锂"}, re.compile("宁德时代|锂电池|碳酸锂")),
    )
    return pipeline


def test_process_one_ocr_fallback_extracts_facts_when_text_too_short(
    tmp_path: Path, monkeypatch
) -> None:
    import market_monitor.report_ocr as report_ocr

    pdf = _fake_pdf(tmp_path)
    pipeline = _patch_pipeline_pdf_and_whitelist(monkeypatch, page_text="扫描页，无有效文本")
    ocr_text = "宁德时代在锂电池产业链中游持续扩产，碳酸锂等原材料成本下降。" * 5
    monkeypatch.setattr(report_ocr, "ocr_pdf_pages", lambda pdf_path: [ocr_text])

    output_root = tmp_path / "out"
    output_root.mkdir()
    result = pipeline._process_one(pdf, output_root, version=4)

    assert result["status"] == "processed"
    assert result["facts"] > 0
    assert result["ocr_applied"] is True
    document = json.loads(
        (output_root / f"{result['report_id']}.json").read_text(encoding="utf-8")
    )
    assert document["ocr_applied"] is True
    assert any("OCR" in warning for warning in document["warnings"])
    assert document["chars"] > 120


def test_process_one_force_reruns_and_replaces_existing_report(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = _fake_pdf(tmp_path)
    page_text = "宁德时代在锂电池产业链中游持续扩产，碳酸锂等原材料成本下降。" * 5
    pipeline = _patch_pipeline_pdf_and_whitelist(monkeypatch, page_text=page_text)
    report_id = "report_" + hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
    output_root = tmp_path / "out"
    output_root.mkdir()
    stale = {
        "schema_version": 1,
        "report_id": report_id,
        "file_name": pdf.name,
        "title": "旧报告",
        "status": "REVIEWED",
        "version": 4,
        "processed_at": "2026-08-09T00:00:00+08:00",
        "pages": 0,
        "chars": 0,
        "facts": [],
        "cooccurrences": [],
        "warnings": ["旧版结果"],
    }
    (output_root / f"{report_id}.json").write_text(
        json.dumps(stale, ensure_ascii=False), encoding="utf-8"
    )

    skipped = pipeline._process_one(pdf, output_root, version=4)
    assert skipped["status"] == "skipped"
    assert skipped["facts"] == 0

    processed = pipeline._process_one(pdf, output_root, version=4, force=True)
    assert processed["status"] == "processed"
    assert processed["facts"] > 0
    assert processed["ocr_applied"] is False

    document = json.loads(
        (output_root / f"{report_id}.json").read_text(encoding="utf-8")
    )
    assert document["facts"]
    assert document["chars"] > 120
    assert document["version"] == 4


def test_process_one_respects_ocr_fallback_disabled(tmp_path: Path, monkeypatch) -> None:
    import market_monitor.report_ocr as report_ocr

    pdf = _fake_pdf(tmp_path)
    pipeline = _patch_pipeline_pdf_and_whitelist(monkeypatch, page_text="短文本")

    def _should_not_call(pdf_path) -> list[str]:
        raise AssertionError("ocr_fallback=False 时不应调用 OCR")

    monkeypatch.setattr(report_ocr, "ocr_pdf_pages", _should_not_call)
    output_root = tmp_path / "out"
    output_root.mkdir()

    result = pipeline._process_one(pdf, output_root, version=4, ocr_fallback=False)

    assert result["status"] == "processed"
    assert result["facts"] == 0
    assert result["ocr_applied"] is False
