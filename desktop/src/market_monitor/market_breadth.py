"""市场宽度（Market Breadth）模块（架构调整任务第七节）。

每日上涨/下跌/涨停/跌停家数、连板高度、昨日涨停今日接盘收益率、
沪深京总市值、当日成交额、北向/南向资金。所有指标均为纯函数，
结果记录 metric_definition / calculation_method / timestamp。
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
    limit_ups: int
    limit_downs: int
    limit_up_heights: dict[str, int]
    total_market_cap: float | None
    total_amount: float | None
    northbound_flow: float | None
    southbound_flow: float | None
    yesterday_limit_up_open_return: float | None
    metric_definition: str = "上涨=close>前收盘；涨停=涨幅>=阈值；连板=连续涨停天数"
    calculation_method: str = "按 trading_day 分组，以 1d bar 计算"
    timestamp: str = ""
    source: str = "local-computed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trading_date": self.trading_date,
            "advances": self.advances,
            "declines": self.declines,
            "unchanged": self.unchanged,
            "limit_ups": self.limit_ups,
            "limit_downs": self.limit_downs,
            "limit_up_heights": dict(self.limit_up_heights),
            "total_market_cap": self.total_market_cap,
            "total_amount": self.total_amount,
            "northbound_flow": self.northbound_flow,
            "southbound_flow": self.southbound_flow,
            "yesterday_limit_up_open_return": self.yesterday_limit_up_open_return,
            "metric_definition": self.metric_definition,
            "calculation_method": self.calculation_method,
            "timestamp": self.timestamp,
            "source": self.source,
        }


def compute_daily_breadth(
    bars_by_day: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    limit_pct: float = 0.10,
    market_caps: Mapping[str, float] | None = None,
    amounts: Mapping[str, float] | None = None,
    northbound_flow: float | None = None,
    southbound_flow: float | None = None,
    now: datetime | None = None,
) -> list[MarketBreadthSnapshot]:
    """按交易日计算市场宽度快照（一个交易日一条）。"""

    if not (0 < limit_pct <= 0.5):
        raise ValueError("limit_pct must be in (0, 0.5]")
    timestamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    snapshots: list[MarketBreadthSnapshot] = []
    previous_by_code: dict[str, float] = {}
    limit_up_by_code_previous: set[str] = set()
    limit_up_heights: dict[str, int] = {}
    for trading_day in sorted(bars_by_day):
        bars = bars_by_day[trading_day]
        advances = declines = unchanged = limit_ups = limit_downs = 0
        limit_up_codes_today: set[str] = set()
        yesterday_limit_up_return: list[float] = []
        for bar in bars:
            code = _code_of(bar)
            close = float(bar["close"])
            open_price = float(bar["open"])
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
            is_limit_up = pct is not None and pct >= limit_pct - 1e-9
            is_limit_down = pct is not None and pct <= -limit_pct + 1e-9
            if is_limit_up:
                limit_ups += 1
                limit_up_codes_today.add(code)
            if is_limit_down:
                limit_downs += 1
            if code in limit_up_by_code_previous:
                if previous is not None and previous > 0 and open_price > 0:
                    yesterday_limit_up_return.append((close - open_price) / open_price)
            previous_by_code[code] = close
        # 只保留当日仍涨停的标的，高度在历史累计值上 +1；断板自动清零
        heights = {code: limit_up_heights.get(code, 0) + 1 for code in limit_up_codes_today}
        limit_up_heights = heights
        limit_up_by_code_previous = limit_up_codes_today
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
        avg_return = sum(yesterday_limit_up_return) / len(yesterday_limit_up_return) if yesterday_limit_up_return else None
        snapshots.append(
            MarketBreadthSnapshot(
                trading_date=trading_day,
                advances=advances,
                declines=declines,
                unchanged=unchanged,
                limit_ups=limit_ups,
                limit_downs=limit_downs,
                limit_up_heights=heights,
                total_market_cap=total_cap,
                total_amount=total_amount,
                northbound_flow=northbound_flow,
                southbound_flow=southbound_flow,
                yesterday_limit_up_open_return=avg_return,
                timestamp=timestamp,
            )
        )
    return snapshots


def compute_limit_up_heights(
    bars_by_day: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    limit_pct: float = 0.10,
) -> dict[str, int]:
    """统计最后一个交易日各标的的连续涨停高度。

    涨停按收盘价相对前一交易日收盘价计算（与 compute_daily_breadth 一致），
    首日无昨收的标的不会被误判为涨停。
    """

    days = sorted(bars_by_day)
    if not days:
        return {}
    heights: dict[str, int] = {}
    previous_close_by_code: dict[str, float] = {}
    for trading_day in days:
        limit_up_today: set[str] = set()
        for bar in bars_by_day[trading_day]:
            close = float(bar["close"])
            previous = previous_close_by_code.get(_code_of(bar))
            if previous is not None and previous > 0 and (close - previous) / previous >= limit_pct - 1e-9:
                limit_up_today.add(_code_of(bar))
            previous_close_by_code[_code_of(bar)] = close
        heights = {code: heights.get(code, 0) + 1 for code in limit_up_today}
    return heights


def _code_of(bar: Mapping[str, Any]) -> str:
    key = bar.get("instrument_key")
    if isinstance(key, Mapping):
        return str(key.get("code", ""))
    return str(bar.get("instrument_id", ""))
