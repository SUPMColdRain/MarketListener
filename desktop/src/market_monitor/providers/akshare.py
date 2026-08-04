"""Real AkShare capability probe for A-share market-wide indicators."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import Capability, CapabilityStatus, ErrorCategory, FetchResult, Provider, ProviderError, SourceDescription, _legacy_adapter_capability
from .joinquant import _error_detail, _provider_error


class AkShareProvider(Provider):
    name = "akshare"
    source_description = SourceDescription(
        "akshare", "AKShare", "Open-source China-market data interface adapter"
    )

    def __init__(self, *, sdk: Any | None = None) -> None:
        self._sdk = sdk

    def probe_capabilities(self) -> Sequence[Capability]:
        try:
            spot = self._spot()
        except ProviderError as error:
            raise error
        capabilities = [_legacy_adapter_capability("health_check", CapabilityStatus.PASS, "A-share spot query succeeded", len(spot))]
        capabilities.append(self._market_breadth(spot))
        capabilities.append(self._price_limit_counts(spot))
        capabilities.append(self._fund_flow())
        return capabilities

    def fetch_instruments(self) -> FetchResult:
        rows = self._spot()
        return FetchResult(records=rows, detail="AkShare A-share spot catalogue")

    def fetch_bars(self) -> FetchResult:
        try:
            frame = self._api().stock_zh_a_hist(symbol="600519", period="daily", adjust="")
            return FetchResult(records=_records(frame), detail="AkShare 600519 daily bars")
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_indicators(self) -> FetchResult:
        try:
            frame = self._api().stock_market_fund_flow()
            return FetchResult(records=_records(frame), detail="AkShare market fund flow")
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_calendar(self) -> FetchResult:
        try:
            frame = self._api().tool_trade_date_hist_sina()
            return FetchResult(records=_records(frame), detail="AkShare trading calendar")
        except Exception as error:
            raise _provider_error(error) from error

    def health_check(self) -> FetchResult:
        rows = self._spot()
        if not rows:
            raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero A-share spot rows")
        return FetchResult(records=rows[:1], detail="A-share spot query succeeded")

    def _spot(self) -> list[Mapping[str, Any]]:
        try:
            records = _records(self._api().stock_zh_a_spot_em())
        except Exception as error:
            raise _provider_error(error) from error
        if not records:
            raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero A-share spot rows")
        return records

    def _market_breadth(self, records: list[Mapping[str, Any]]) -> Capability:
        try:
            changes = [_number(record, "涨跌幅") for record in records]
            usable = [change for change in changes if change is not None]
            if not usable:
                raise ProviderError(ErrorCategory.FIELD_CHANGE, "AkShare spot response has no 涨跌幅 field")
            up = sum(change > 0 for change in usable)
            down = sum(change < 0 for change in usable)
            return _legacy_adapter_capability("a_share_rise_fall_counts", CapabilityStatus.PASS, f"up={up}; down={down}; flat={len(usable) - up - down}", len(usable))
        except ProviderError as error:
            return _legacy_adapter_capability("a_share_rise_fall_counts", CapabilityStatus.FAILED, _error_detail(error))

    def _price_limit_counts(self, records: list[Mapping[str, Any]]) -> Capability:
        try:
            changes = [_number(record, "涨跌幅") for record in records]
            usable = [change for change in changes if change is not None]
            if not usable:
                raise ProviderError(ErrorCategory.FIELD_CHANGE, "AkShare spot response has no 涨跌幅 field")
            limit_up = sum(change >= 9.9 for change in usable)
            limit_down = sum(change <= -9.9 for change in usable)
            return _legacy_adapter_capability("a_share_price_limit_counts", CapabilityStatus.PASS, f"limit_up={limit_up}; limit_down={limit_down}", len(usable))
        except ProviderError as error:
            return _legacy_adapter_capability("a_share_price_limit_counts", CapabilityStatus.FAILED, _error_detail(error))

    def _fund_flow(self) -> Capability:
        try:
            response = self.fetch_indicators()
            if not response.records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "AkShare returned zero market fund-flow rows")
            return _legacy_adapter_capability("market_fund_flow", CapabilityStatus.PASS, response.detail, len(response.records))
        except ProviderError as error:
            return _legacy_adapter_capability("market_fund_flow", CapabilityStatus.FAILED, _error_detail(error))

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


def _number(record: Mapping[str, Any], field: str) -> float | None:
    value = record.get(field)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
