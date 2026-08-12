"""Regression coverage for resumable full-market stock backfills."""

from __future__ import annotations

import json
from pathlib import Path

from market_monitor import full_market


def test_full_stock_backfill_persists_chinese_checkpoint_and_resumes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        full_market,
        "_universe",
        lambda _root, _market: [{"code": "000001", "name": "样本甲"}, {"code": "000002", "name": "样本乙"}],
    )

    def fetcher(_market: str, _code: str, _start_date: str):
        return [{"日期": "2026-08-10", "开盘": 10, "最高": 12, "最低": 9, "收盘": 11, "成交量": 100, "成交额": 1100}]

    first = full_market.run_full_stock_backfill(tmp_path, market="CN", workers=1, batch_size=1, pause_seconds=0.1, fetcher=fetcher)
    assert first["状态"] == "完成"
    assert first["市场"]["CN"]["已完成"] == 2
    state = json.loads((tmp_path / "bulk_stock" / "cn_state.json").read_text(encoding="utf-8"))
    assert state["状态"] == "完成"
    assert state["已完成代码"] == ["000001", "000002"]

    second = full_market.run_full_stock_backfill(tmp_path, market="CN", workers=1, batch_size=1, pause_seconds=0.1, fetcher=fetcher)
    assert second["市场"]["CN"]["待处理"] == 0
