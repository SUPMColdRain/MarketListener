"""产业链研报知识库流水线：聚合、核验与 SVG 图谱生成的轻量回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

from market_monitor.report_pipeline import (
    build_chain_index,
    build_industry_map_html,
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
    assert (output_root / "industry-map.html").is_file()


def test_industry_map_html_contains_svg_and_snapshot(tmp_path: Path) -> None:
    output_root = tmp_path / "industry"
    output_root.mkdir()
    _write_report(
        output_root,
        "e5f6",
        primary_chain="锂电池",
        related_chains=[],
        facts=[
            _fact("宁德时代", "COMPANY", "锂电池"),
            _fact("磷酸铁锂", "PRODUCT", "锂电池"),
        ],
    )
    index = build_chain_index(output_root)
    target = tmp_path / "industry-map.html"
    snapshot = tmp_path / "snapshots" / "industry-map.html"

    written = build_industry_map_html(output_root, html_path=target, snapshot_path=snapshot, index=index)

    assert written == target
    html = target.read_text(encoding="utf-8")
    assert "<svg" in html
    assert "锂电池" in html
    assert "宁德时代" in html
    assert "window.INDEX" in html
    assert "产业链图谱 · 研报知识库" in html
    assert snapshot.read_text(encoding="utf-8") == html


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
