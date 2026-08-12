"""Real AkShare capability probe for A-share market-wide indicators.

The adapter prefers Eastmoney endpoints but falls back to Tencent and Sina
when the primary source is unreachable, so one provider outage does not turn
the whole adapter into a failure.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping, Sequence

from .base import (
    Capability,
    CapabilityStatus,
    ErrorCategory,
    FetchResult,
    Provider,
    ProviderError,
    SourceDescription,
    _legacy_adapter_capability,
)
from .joinquant import _error_detail, _provider_error

_BAR_FIELDS = {
    "日期": "date",
    "股票代码": "code",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}

_TX_SPOT_FIELDS = {
    "code": "代码",
    "name": "名称",
    "zdf": "涨跌幅",
    "zd": "涨跌额",
}


class AkShareProvider(Provider):
    name = "akshare"
    source_description = SourceDescription(
        "akshare",
        "AKShare",
        "Open-source China-market adapter with Eastmoney/Tencent/Sina fallbacks",
    )

    def __init__(self, *, sdk: Any | None = None) -> None:
        self._sdk = sdk

    def probe_capabilities(self) -> Sequence[Capability]:
        capabilities: list[Capability] = []
        capabilities.extend(self._probe_snapshot())
        capabilities.append(self._probe_calendar())
        capabilities.append(self._fund_flow())
        capabilities.append(self._probe_bars())
        return capabilities

    def fetch_instruments(self) -> FetchResult:
        rows = self._spot()
        return FetchResult(records=rows, detail="AkShare A-share spot catalogue")

    def fetch_bars(self) -> FetchResult:
        records, detail = self._bars_with_detail()
        dates = [str(row["date"]) for row in records if row.get("date")]
        return FetchResult(
            records=records,
            earliest=min(dates) if dates else None,
            latest=max(dates) if dates else None,
            detail=detail,
        )

    def fetch_indicators(self) -> FetchResult:
        try:
            frame = self._api().stock_market_fund_flow()
            return FetchResult(records=_records(frame), detail="AkShare market fund flow (Eastmoney)")
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_calendar(self) -> FetchResult:
        try:
            frame = self._api().tool_trade_date_hist_sina()
            return FetchResult(records=_records(frame), detail="AkShare trading calendar (Sina)")
        except Exception as error:
            raise _provider_error(error) from error

    def health_check(self) -> FetchResult:
        rows = self._spot()
        if not rows:
            raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero A-share spot rows")
        return FetchResult(records=rows[:1], detail="A-share spot query succeeded")

    def _spot(self) -> list[Mapping[str, Any]]:
        records, _ = self._call_fallbacks(
            (
                ("stock_zh_a_spot_em", {}),
                ("stock_zh_a_spot_tx", {}),
                ("stock_zh_a_spot", {}),
            ),
            "AkShare returned zero A-share spot rows",
            _normalise_spot,
        )
        return records

    def _bars_with_detail(self) -> tuple[list[Mapping[str, Any]], str]:
        today = date.today().isoformat().replace("-", "")
        records, source = self._call_fallbacks(
            (
                ("stock_zh_a_hist", {"symbol": "600519", "period": "daily", "adjust": "qfq"}),
                ("stock_zh_a_daily", {"symbol": "sh600519", "adjust": "qfq"}),
                (
                    "stock_zh_a_hist_tx",
                    {"symbol": "sh600519", "start_date": "20240101", "end_date": today, "adjust": "qfq"},
                ),
            ),
            "AkShare returned zero daily bars",
            _normalise_bars,
        )
        return records, f"AkShare 600519 daily bars via {source}"

    def _call_fallbacks(
        self,
        calls: Sequence[tuple[str, Mapping[str, Any]]],
        empty_message: str,
        normalise: Callable[[list[Mapping[str, Any]], str], list[Mapping[str, Any]]],
    ) -> tuple[list[Mapping[str, Any]], str]:
        last_error: Exception | None = None
        api = self._api()
        for name, kwargs in calls:
            function = getattr(api, name, None)
            if function is None:
                continue
            try:
                records = _records(function(**kwargs))
            except Exception as error:
                last_error = error
                continue
            if not records:
                continue
            return normalise(records, name), name
        if last_error is not None:
            raise _provider_error(last_error) from last_error
        raise ProviderError(ErrorCategory.NO_COVERAGE, empty_message)

    def _probe_snapshot(self) -> list[Capability]:
        try:
            spot = self._spot()
        except ProviderError as error:
            return [
                _legacy_adapter_capability(
                    "health_check",
                    CapabilityStatus.FAILED,
                    _error_detail(error),
                    error=error,
                )
            ]
        capabilities = [
            _legacy_adapter_capability(
                "health_check",
                CapabilityStatus.PASS,
                "A-share spot query succeeded",
                len(spot),
            )
        ]
        capabilities.append(self._market_breadth(spot))
        return capabilities

    def _probe_calendar(self) -> Capability:
        try:
            response = self.fetch_calendar()
            if not response.records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero trading-calendar rows")
            return _legacy_adapter_capability(
                "trading_calendar",
                CapabilityStatus.PASS,
                response.detail,
                len(response.records),
            )
        except ProviderError as error:
            return _legacy_adapter_capability(
                "trading_calendar",
                CapabilityStatus.FAILED,
                _error_detail(error),
                error=error,
            )

    def _probe_bars(self) -> Capability:
        try:
            response = self.fetch_bars()
            if not response.records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero daily bars")
            return _legacy_adapter_capability(
                "cn_stock_sh.600519_1d",
                CapabilityStatus.PASS,
                response.detail,
                len(response.records),
            )
        except ProviderError as error:
            return _legacy_adapter_capability(
                "cn_stock_sh.600519_1d",
                CapabilityStatus.FAILED,
                _error_detail(error),
                error=error,
            )

    def _market_breadth(self, records: list[Mapping[str, Any]]) -> Capability:
        try:
            changes = [_number(record, "涨跌幅") for record in records]
            usable = [change for change in changes if change is not None]
            if not usable:
                raise ProviderError(ErrorCategory.FIELD_CHANGE, "AkShare spot response has no 涨跌幅 field")
            up = sum(change > 0 for change in usable)
            down = sum(change < 0 for change in usable)
            return _legacy_adapter_capability(
                "a_share_rise_fall_counts",
                CapabilityStatus.PASS,
                f"up={up}; down={down}; flat={len(usable) - up - down}",
                len(usable),
            )
        except ProviderError as error:
            return _legacy_adapter_capability(
                "a_share_rise_fall_counts",
                CapabilityStatus.FAILED,
                _error_detail(error),
                error=error,
            )

    def _fund_flow(self) -> Capability:
        try:
            response = self.fetch_indicators()
            if not response.records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero market fund-flow rows")
            return _legacy_adapter_capability("market_fund_flow", CapabilityStatus.PASS, response.detail, len(response.records))
        except ProviderError as error:
            return _legacy_adapter_capability(
                "market_fund_flow",
                CapabilityStatus.FAILED,
                _error_detail(error),
                error=error,
            )

    def _api(self) -> Any:
        if self._sdk is not None:
            return self._sdk
        try:
            import akshare
        except ImportError as error:
            raise ProviderError(ErrorCategory.UNKNOWN, "akshare is not installed") from error
        self._sdk = akshare
        return self._sdk


def _records(value: Any) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return list(value.to_dict(orient="records"))
        except TypeError:
            pass
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [item if isinstance(item, Mapping) else {"value": item} for item in value]
    return [{"value": value}]


def _normalise_spot(records: list[Mapping[str, Any]], source: str) -> list[Mapping[str, Any]]:
    fields = _TX_SPOT_FIELDS if source == "stock_zh_a_spot_tx" else {}
    if not fields:
        return records
    return [{fields.get(key, key): value for key, value in row.items()} for row in records]


def _normalise_bars(records: list[Mapping[str, Any]], source: str) -> list[Mapping[str, Any]]:
    del source
    return [_normalise_bar(row) for row in records]


def _normalise_bar(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Map AkShare Chinese or English bar columns to the cross-source names."""

    normalised: dict[str, Any] = {}
    for key, value in row.items():
        mapped = _BAR_FIELDS.get(key, key)
        if mapped == "date" and not isinstance(value, str):
            value = value.isoformat() if hasattr(value, "isoformat") else str(value)
        normalised[mapped] = value
    return normalised


def _number(record: Mapping[str, Any], field: str) -> float | None:
    value = record.get(field)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
