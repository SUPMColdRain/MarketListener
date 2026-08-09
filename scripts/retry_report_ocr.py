"""研报重试工具：补处理无报告的 PDF，OCR 重试零事实扫描件，标记缺失源文件。

用法（在仓库根目录执行）:
    desktop\\.venv\\Scripts\\python scripts\\retry_report_ocr.py

可选参数:
    --report-root <目录>     研报 PDF 根目录（默认 行业产业链研报）
    --output-root <目录>     报告 JSON 输出目录（默认 reports/industry）
    --version <整数>         流水线版本号（默认 4）
    --no-rebuild             不重建 chain_index / HTML
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "desktop" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_monitor.report_pipeline import (  # noqa: E402
    _process_one,
    build_chain_index,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_report(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="研报重试 / OCR 补偿工具")
    parser.add_argument("--report-root", default=str(ROOT / "行业产业链研报"))
    parser.add_argument("--output-root", default=str(ROOT / "reports" / "industry"))
    parser.add_argument("--version", type=int, default=4)
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()

    report_root = Path(args.report_root)
    output_root = Path(args.output_root)
    if not report_root.is_dir():
        print(f"研报目录不存在: {report_root}")
        return 2

    pdfs = {p.name: p for p in report_root.rglob("*.pdf")}
    report_paths = sorted(output_root.glob("report_*.json"))
    reports = [(_load_report(p), p) for p in report_paths]
    reports = [(d, p) for d, p in reports if d]
    report_by_file = {}
    for d, p in reports:
        report_by_file[d.get("file_name", "")] = (d, p)

    processed = []
    ocr_retried = []
    marked_missing = []
    skipped = []

    # 1) PDF 存在但没有报告 JSON -> 正常处理（自动 OCR 补偿）
    for name, pdf in sorted(pdfs.items()):
        if name not in report_by_file:
            result = _process_one(pdf, output_root, args.version, ocr_fallback=True)
            processed.append((name, result.get("status"), result.get("facts"), result.get("ocr_applied", False)))

    # 2) 报告 JSON 存在但 facts==0 -> force 重跑（扫描件走 OCR）
    for d, p in reports:
        if len(d.get("facts", [])) != 0:
            continue
        name = d.get("file_name", "")
        pdf = pdfs.get(name)
        if pdf is None:
            if not d.get("source_missing"):
                d["source_missing"] = True
                d["source_missing_at"] = _utcnow()
                p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            marked_missing.append((name, "zero-fact source missing"))
            continue
        result = _process_one(pdf, output_root, args.version, force=True, ocr_fallback=True)
        ocr_retried.append((name, result.get("status"), result.get("facts"), result.get("ocr_applied", False)))

    # 3) 报告 JSON 存在但 PDF 缺失 -> 标记 source_missing（保留已有事实）
    for d, p in reports:
        name = d.get("file_name", "")
        if name in pdfs:
            continue
        if not d.get("source_missing"):
            d["source_missing"] = True
            d["source_missing_at"] = _utcnow()
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        marked_missing.append((name, "source missing"))

    print("== 新处理 ==")
    for row in processed:
        print(row)
    print("== OCR 重试 ==")
    for row in ocr_retried:
        print(row)
    print("== 标记缺失 ==")
    for row in marked_missing:
        print(row)

    if not args.no_rebuild:
        print("== 重建 chain_index / HTML ==")
        index = build_chain_index(output_root, max_facts_per_chain=200)
        print(
            "chains=", index.get("chain_count"),
            "reports=", index.get("report_count"),
            "facts=", index.get("fact_count"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
