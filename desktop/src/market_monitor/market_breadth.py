"""市场宽度（Market Breadth）模块（架构调整任务第七节）。

每日上涨/下跌/平盘家数、沪深京总市值、当日成交额、北向/南向资金。
涨停/跌停、连板高度和昨日涨停接盘收益率必须来自权威涨停池或带证券属性、
生效日期的规则模型，不能由本模块的统一百分比阈值推算。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MarketBreadthSnapshot:
    trading_date: str
    advances: int
    declines: int
    unchanged: int
    total_market_cap: float | None
    total_amount: float | None
    northbound_flow: float | None
    southbound_flow: float | None
    metric_definition: str = "上涨=close>前收盘；下跌=close<前收盘；平盘=close=前收盘"
    calculation_method: str = "按 trading_day 分组，以 1d bar 计算"
    timestamp: str = ""
    source: str = "local-computed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trading_date": self.trading_date,
            "advances": self.advances,
            "declines": self.declines,
            "unchanged": self.unchanged,
            "total_market_cap": self.total_market_cap,
            "total_amount": self.total_amount,
            "northbound_flow": self.northbound_flow,
            "southbound_flow": self.southbound_flow,
            "metric_definition": self.metric_definition,
            "calculation_method": self.calculation_method,
            "timestamp": self.timestamp,
            "source": self.source,
        }


def compute_daily_breadth(
    bars_by_day: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    market_caps: Mapping[str, float] | None = None,
    amounts: Mapping[str, float] | None = None,
    northbound_flow: float | None = None,
    southbound_flow: float | None = None,
    now: datetime | None = None,
) -> list[MarketBreadthSnapshot]:
    """按交易日计算市场宽度快照（一个交易日一条）。"""

    timestamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    snapshots: list[MarketBreadthSnapshot] = []
    previous_by_code: dict[str, float] = {}
    for trading_day in sorted(bars_by_day):
        bars = bars_by_day[trading_day]
        advances = declines = unchanged = 0
        for bar in bars:
            code = _code_of(bar)
            close = float(bar["close"])
            previous = previous_by_code.get(code)
            pct = None if previous is None or previous == 0 else (close - previous) / previous
            if pct is None:
                pass
            elif pct > 0:
                advances += 1
            elif pct < 0:
                declines += 1
            else:
                unchanged += 1
            previous_by_code[code] = close
        total_cap = (
            sum(cap for code, cap in (market_caps or {}).items() if code in {_code_of(bar) for bar in bars})
            if market_caps is not None
            else None
        )
        total_amount = (
            sum(amount for code, amount in (amounts or {}).items() if code in {_code_of(bar) for bar in bars})
            if amounts is not None
            else None
        )
        snapshots.append(
            MarketBreadthSnapshot(
                trading_date=trading_day,
                advances=advances,
                declines=declines,
                unchanged=unchanged,
                total_market_cap=total_cap,
                total_amount=total_amount,
                northbound_flow=northbound_flow,
                southbound_flow=southbound_flow,
                timestamp=timestamp,
            )
        )
    return snapshots
def _code_of(bar: Mapping[str, Any]) -> str:
    key = bar.get("instrument_key")
    if isinstance(key, Mapping):
        return str(key.get("code", ""))
    return str(bar.get("instrument_id", ""))
