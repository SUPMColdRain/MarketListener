"""Market expansion: HK samples, futures continuous contracts, market indicators.

All domain rules are deterministic and unit-tested with fixed samples.  Real
provider probing is separate and reports PASS/BLOCKED/FAILED with the actual
row range; a failing endpoint never fabricates coverage.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence


HK_SAMPLE_INSTRUMENTS: tuple[tuple[str, str, str], ...] = (
    ("00700", "HKEX", "腾讯控股"),
    ("00005", "HKEX", "汇丰控股"),
    ("09988", "HKEX", "阿里巴巴-W"),
)


def normalize_hk_bar(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize AKShare ``stock_hk_hist`` columns to canonical English fields."""

    aliases = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    output: dict[str, Any] = {}
    for source_name, target_name in aliases.items():
        if source_name in row:
            output[target_name] = row[source_name]
    for target_name in ("open", "high", "low", "close", "volume", "amount"):
        output.setdefault(target_name, 0.0)
    return output


@dataclass(frozen=True)
class FuturesContract:
    symbol: str
    exchange: str
    expiry_month: date
    open_interest: float = 0.0
    volume: float = 0.0


def select_main_contract(contracts: Sequence[FuturesContract]) -> FuturesContract | None:
    """Main contract = highest open interest, then volume, then nearest expiry."""

    if not contracts:
        return None
    return max(
        contracts,
        key=lambda contract: (contract.open_interest, contract.volume, -contract.expiry_month.toordinal()),
    )


@dataclass(frozen=True)
class ContinuousBar:
    trading_day: date
    contract_symbol: str
    close: float
    is_roll_day: bool
    roll_gap: float


def build_continuous_series(
    contracts_by_day: Mapping[date, Sequence[FuturesContract]],
    closes: Mapping[tuple[date, str], float],
) -> list[ContinuousBar]:
    """Splice main contracts per trading day; mark roll days with the gap.

    The splice is *unadjusted* by design: each bar keeps the main contract's
    raw close and the roll gap is reported explicitly instead of silently
    adjusting history.  Futures strategies must consume ``roll_gap``/roll-day
    markers to avoid phantom returns across contract switches.
    """

    output: list[ContinuousBar] = []
    previous_symbol: str | None = None
    for trading_day in sorted(contracts_by_day):
        main = select_main_contract(contracts_by_day[trading_day])
        if main is None:
            continue
        close = closes.get((trading_day, main.symbol))
        if close is None:
            continue
        is_roll = previous_symbol is not None and main.symbol != previous_symbol
        gap = 0.0
        if is_roll and output:
            gap = close - output[-1].close
        output.append(
            ContinuousBar(
                trading_day=trading_day,
                contract_symbol=main.symbol,
                close=close,
                is_roll_day=is_roll,
                roll_gap=gap,
            )
        )
        previous_symbol = main.symbol
    return output


@dataclass(frozen=True)
class EtfShare:
    code: str
    exchange: str
    underlying: str
    share_class: str = "PRIMARY"


_EXCHANGE_PRIORITY = {"SH": 0, "SZ": 1, "HK": 2}


def deduplicate_etfs(shares: Sequence[EtfShare]) -> list[EtfShare]:
    """One canonical ETF per (underlying, share class) with deterministic priority."""

    best: dict[tuple[str, str], EtfShare] = {}
    for share in sorted(shares, key=lambda item: (item.code, item.exchange)):
        key = (share.underlying, share.share_class)
        current = best.get(key)
        if current is None or _EXCHANGE_PRIORITY.get(share.exchange, 99) < _EXCHANGE_PRIORITY.get(current.exchange, 99):
            best[key] = share
    return [best[key] for key in sorted(best)]


@dataclass(frozen=True)
class MarketIndicator:
    code: str
    name: str
    definition: str
    unit: str
    frequency: str
    source: str
    data_cutoff: str | None = None
    value: float | None = None

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        for field in ("code", "name", "definition", "unit", "frequency", "source"):
            if not getattr(self, field).strip():
                errors.append(f"{field} 不能为空")
        if self.data_cutoff:
            try:
                datetime.fromisoformat(self.data_cutoff.replace("Z", "+00:00"))
            except ValueError:
                errors.append("data_cutoff 必须是 ISO 时间")
        return errors


THS_INDEX_SAMPLE: tuple[tuple[str, str, str], ...] = (
    ("884116", "白酒指数", "同花顺白酒行业指数（成分股按同花顺行业分类）"),
    ("884039", "半导体指数", "同花顺半导体行业指数"),
    ("884072", "医疗器械指数", "同花顺医疗器械行业指数"),
)


def probe_hk_daily(symbol: str, *, timeout_seconds: int = 30) -> dict[str, Any]:
    """Real AKShare HK daily probe; always returns a status record."""

    def call() -> list[Mapping[str, Any]]:
        import akshare as ak

        frame = ak.stock_hk_hist(symbol=symbol, period="daily", adjust="")
        return frame.to_dict("records")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(call)
        try:
            rows = future.result(timeout=timeout_seconds)
        except FutureTimeout:
            return {"status": "FAILED", "category": "NETWORK", "message": f"timeout after {timeout_seconds}s", "rows": 0}
        except Exception as error:  # noqa: BLE001
            return {"status": "FAILED", "category": "NETWORK", "message": str(error), "rows": 0}
    if not rows:
        return {"status": "NO_COVERAGE", "rows": 0}
    dates = [str(row.get("日期", "")) for row in rows if row.get("日期")]
    return {
        "status": "PASS",
        "rows": len(rows),
        "earliest": min(dates) if dates else None,
        "latest": max(dates) if dates else None,
    }
