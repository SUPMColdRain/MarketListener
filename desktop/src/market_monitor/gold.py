"""Gold 层派生指标：涨跌幅/振幅与常用技术指标。

所有指标都是纯函数，定义与计算方法随结果一起登记（DERIVED_METRIC 数据集），
禁止输出无来源、无方法的派生值。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from market_monitor.aggregation import _instrument_id


SUPPORTED_INDICATORS = frozenset({"sma", "ema", "roc", "stddev", "rolling_max", "rolling_min"})


@dataclass(frozen=True)
class GoldMetric:
    metric_id: str
    instrument_id: str
    trading_date: str
    period: str
    metric_name: str
    value: float
    definition: str
    calculation_method: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "instrument_id": self.instrument_id,
            "trading_date": self.trading_date,
            "period": self.period,
            "metric_name": self.metric_name,
            "value": self.value,
            "definition": self.definition,
            "calculation_method": self.calculation_method,
            "timestamp": self.timestamp,
        }


def enrich_bars(bars: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """为有序 K 线补充 pct_change / amplitude 派生字段（不修改输入）。"""

    output: list[dict[str, Any]] = []
    previous_close: float | None = None
    for raw in bars:
        bar = dict(raw)
        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        if previous_close is not None and previous_close > 0:
            bar["pct_change"] = (close - previous_close) / previous_close
            bar["amplitude"] = (high - low) / previous_close
        else:
            bar["pct_change"] = None
            bar["amplitude"] = None
        previous_close = close
        output.append(bar)
    return output


def compute_gold_metrics(
    bars: Sequence[Mapping[str, Any]],
    *,
    indicators: Sequence[str] = ("sma", "ema", "roc", "stddev"),
    window: int = 10,
    now: datetime | None = None,
) -> list[GoldMetric]:
    """对单标的的日线序列计算一组 Gold 指标。"""

    unknown = set(indicators) - SUPPORTED_INDICATORS
    if unknown:
        raise ValueError(f"unsupported indicators: {sorted(unknown)}")
    if window < 1:
        raise ValueError("window must be >= 1")
    enriched = enrich_bars(bars)
    instrument_id = _instrument_id(bars[0]) if bars else "unknown"
    timestamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    metrics: list[GoldMetric] = []
    closes = [float(bar["close"]) for bar in enriched]
    for index, bar in enumerate(enriched):
        trading_date = str(bar["trading_day"])
        period = str(bar.get("period", "1d"))
        for name in indicators:
            value = _indicator_value(name, closes, index, window)
            if value is None:
                continue
            metric_id = f"{instrument_id}|{trading_date}|{period}|{name}|w{window}"
            metrics.append(
                GoldMetric(
                    metric_id=metric_id,
                    instrument_id=instrument_id,
                    trading_date=trading_date,
                    period=period,
                    metric_name=name,
                    value=value,
                    definition=_definition(name, window),
                    calculation_method=f"window={window}, closes=ordered by bar_open_time",
                    timestamp=timestamp,
                )
            )
    return metrics


def _indicator_value(name: str, closes: Sequence[float], index: int, window: int) -> float | None:
    start = index - window + 1
    if start < 0:
        return None
    values = closes[start:index + 1]
    if name == "sma":
        return sum(values) / len(values)
    if name == "ema":
        return _ema(values, window)
    if name == "roc":
        previous = closes[index - window]
        if previous == 0:
            return None
        return (closes[index] - previous) / previous
    if name == "stddev":
        mean = sum(values) / len(values)
        return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5
    if name == "rolling_max":
        return max(values)
    if name == "rolling_min":
        return min(values)
    raise ValueError(f"unsupported indicator: {name}")  # pragma: no cover


def _ema(values: Sequence[float], window: int) -> float:
    multiplier = 2.0 / (window + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _definition(name: str, window: int) -> str:
    return {
        "sma": f"{window} 日简单移动平均（收盘价）",
        "ema": f"{window} 日指数移动平均（收盘价，平滑系数 2/({window}+1)）",
        "roc": f"{window} 日变化率 (close[t]-close[t-{window}])/close[t-{window}]",
        "stddev": f"{window} 日收盘价标准差（总体标准差）",
        "rolling_max": f"过去 {window} 日收盘价最大值",
        "rolling_min": f"过去 {window} 日收盘价最小值",
    }[name]

