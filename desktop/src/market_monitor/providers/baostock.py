"""Real Baostock capability probe for public A-share data."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Mapping, Sequence

from .base import Capability, CapabilityStatus, ErrorCategory, FetchResult, Provider, ProviderError
from .joinquant import _error_detail, _provider_error


class BaostockProvider(Provider):
    name = "baostock"
    _symbols = ("sh.600519", "sz.000001")

    def __init__(self, *, sdk: Any | None = None, today: Callable[[], date] = date.today) -> None:
        self._sdk = sdk
        self._today = today
        self._logged_in = False

    def probe_capabilities(self) -> Sequence[Capability]:
        self._login()
        capabilities = [self._probe_calendar()]
        for symbol in self._symbols:
            capabilities.append(self._probe_bars(f"cn_stock_{symbol}_1d", symbol, "d"))
            capabilities.append(self._probe_bars(f"cn_stock_{symbol}_30m", symbol, "30"))
            capabilities.append(self._probe_adjust_factor(symbol))
        return capabilities

    def fetch_instruments(self) -> FetchResult:
        self._login()
        try:
            result = self._api().query_all_stock(day=self._today().isoformat())
            return FetchResult(records=_rows(result), detail="Baostock stock catalogue")
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_bars(self) -> FetchResult:
        self._login()
        return self._bars(self._symbols[0], "d")

    def fetch_indicators(self) -> FetchResult:
        self._login()
        return self._adjust_factor(self._symbols[0])

    def fetch_calendar(self) -> FetchResult:
        self._login()
        end = self._today()
        try:
            result = self._api().query_trade_dates(
                start_date=(end - timedelta(days=60)).isoformat(), end_date=end.isoformat()
            )
            return FetchResult(records=_rows(result), detail="Baostock trading calendar")
        except Exception as error:
            raise _provider_error(error) from error

    def health_check(self) -> FetchResult:
        self._login()
        calendar = self.fetch_calendar()
        if not calendar.records:
            raise ProviderError(ErrorCategory.NO_COVERAGE, "Baostock returned no trading calendar rows")
        return FetchResult(records=calendar.records[-1:], detail="public login and calendar query succeeded")

    def _probe_calendar(self) -> Capability:
        try:
            response = self.health_check()
            return Capability("trading_calendar", CapabilityStatus.PASS, response.detail, row_count=len(response.records))
        except ProviderError as error:
            return Capability("trading_calendar", CapabilityStatus.FAILED, _error_detail(error))

    def _probe_bars(self, name: str, symbol: str, frequency: str) -> Capability:
        try:
            response = self._bars(symbol, frequency)
            if not response.records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Baostock returned zero rows")
            return Capability(name, CapabilityStatus.PASS, f"frequency={frequency}", len(response.records))
        except ProviderError as error:
            return Capability(name, CapabilityStatus.FAILED, _error_detail(error))

    def _probe_adjust_factor(self, symbol: str) -> Capability:
        try:
            response = self._adjust_factor(symbol)
            if not response.records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Baostock returned zero adjustment factors")
            return Capability(f"adjust_factor_{symbol}", CapabilityStatus.PASS, row_count=len(response.records))
        except ProviderError as error:
            return Capability(f"adjust_factor_{symbol}", CapabilityStatus.FAILED, _error_detail(error))

    def _bars(self, symbol: str, frequency: str) -> FetchResult:
        end = self._today()
        try:
            result = self._api().query_history_k_data_plus(
                symbol,
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=(end - timedelta(days=60)).isoformat(),
                end_date=end.isoformat(),
                frequency=frequency,
                adjustflag="3",
            )
            rows = _rows(result)
            return FetchResult(records=rows, detail=f"Baostock {symbol} frequency={frequency}")
        except Exception as error:
            raise _provider_error(error) from error

    def _adjust_factor(self, symbol: str) -> FetchResult:
        end = self._today()
        try:
            result = self._api().query_adjust_factor(
                code=symbol,
                start_date=(end - timedelta(days=60)).isoformat(),
                end_date=end.isoformat(),
            )
            return FetchResult(records=_rows(result), detail=f"Baostock adjustment factors for {symbol}")
        except Exception as error:
            raise _provider_error(error) from error

    def _login(self) -> None:
        if self._logged_in:
            return
        try:
            result = self._api().login()
        except Exception as error:
            raise _provider_error(error) from error
        if str(getattr(result, "error_code", "-1")) != "0":
            raise _provider_error(RuntimeError(str(getattr(result, "error_msg", "Baostock login failed"))))
        self._logged_in = True

    def _api(self) -> Any:
        if self._sdk is not None:
            return self._sdk
        try:
            import baostock
        except ImportError as error:
            raise ProviderError(ErrorCategory.UNKNOWN, "baostock is not installed") from error
        self._sdk = baostock
        return self._sdk


def _rows(result: Any) -> list[Mapping[str, str]]:
    if str(getattr(result, "error_code", "-1")) != "0":
        raise _provider_error(RuntimeError(str(getattr(result, "error_msg", "Baostock query failed"))))
    fields = list(getattr(result, "fields", []))
    rows: list[Mapping[str, str]] = []
    while result.next():
        values = result.get_row_data()
        rows.append(dict(zip(fields, values, strict=False)))
    return rows
