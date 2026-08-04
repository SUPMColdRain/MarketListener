"""Real JoinQuant/JQData capability probe with source-specific symbol mapping."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Callable, Mapping, Sequence

from .base import Capability, CapabilityStatus, ErrorCategory, FetchResult, Provider, ProviderError, SourceDescription, _legacy_adapter_capability


class JoinQuantProvider(Provider):
    name = "joinquant"
    source_description = SourceDescription(
        "joinquant", "JoinQuant / JQData", "Credential-gated China-market data interface adapter"
    )
    _stock_symbols = ("600519.XSHG", "000001.XSHE")
    _etf_symbols = ("510300.XSHG", "159915.XSHE")
    _index_symbol = "000300.XSHG"
    _periods = (("1d", "daily"), ("30m", "30m"), ("1m", "1m"))

    def __init__(
        self,
        *,
        sdk: Any | None = None,
        username: str | None = None,
        password: str | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._sdk = sdk
        self._username = username if username is not None else os.getenv("JQDATA_USERNAME")
        self._password = password if password is not None else os.getenv("JQDATA_PASSWORD")
        self._today = today
        self._authenticated = False

    def probe_capabilities(self) -> Sequence[Capability]:
        self._authenticate()
        capabilities: list[Capability] = [self._probe_health()]
        for label, symbols in (("cn_stock", self._stock_symbols), ("cn_etf", self._etf_symbols)):
            for period_name, frequency in self._periods:
                for symbol in symbols:
                    capabilities.append(self._probe_bars(f"{label}_{symbol}_{period_name}", symbol, frequency))
        for period_name, frequency in self._periods:
            capabilities.append(self._probe_bars(f"cn_index_{period_name}", self._index_symbol, frequency))

        future = self._discover_current_future()
        if future is None:
            capabilities.append(
                _legacy_adapter_capability("cn_future_discovery", CapabilityStatus.UNSUPPORTED, "No current future contract returned")
            )
        else:
            capabilities.append(_legacy_adapter_capability("cn_future_discovery", CapabilityStatus.PASS, future))
            for period_name, frequency in self._periods:
                capabilities.append(self._probe_bars(f"cn_future_{future}_{period_name}", future, frequency))
        return capabilities

    def fetch_instruments(self) -> FetchResult:
        self._authenticate()
        try:
            result = self._api().get_all_securities(date=self._today())
            return FetchResult(records=_records(result), detail="JoinQuant securities catalogue")
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_bars(self) -> FetchResult:
        self._authenticate()
        try:
            result = self._get_price(self._stock_symbols[0], "daily")
            records = _records(result)
            index = getattr(result, "index", None)
            if index is not None and not callable(index):
                for row, timestamp in zip(records, index, strict=False):
                    row["time"] = _as_timestamp(timestamp)
            return FetchResult(
                records=records,
                earliest=_first_timestamp(result),
                latest=_last_timestamp(result),
                detail=f"JoinQuant {self._stock_symbols[0]} daily bars",
            )
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_indicators(self) -> FetchResult:
        self._authenticate()
        api = self._api()
        if not hasattr(api, "get_extras"):
            raise ProviderError(ErrorCategory.NO_COVERAGE, "JoinQuant SDK has no adjustment-factor API")
        try:
            end = self._today()
            result = api.get_extras(
                "factor",
                security_list=[self._stock_symbols[0]],
                start_date=end - timedelta(days=60),
                end_date=end,
                df=True,
            )
            return FetchResult(records=_records(result), detail="JoinQuant adjustment factors")
        except Exception as error:
            raise _provider_error(error) from error

    def fetch_calendar(self) -> FetchResult:
        self._authenticate()
        try:
            days = self._api().get_trade_days(end_date=self._today(), count=30)
            return FetchResult(records=[{"trading_day": str(day)} for day in days], detail="JoinQuant trading days")
        except Exception as error:
            raise _provider_error(error) from error

    def health_check(self) -> FetchResult:
        self._authenticate()
        try:
            days = self._api().get_trade_days(end_date=self._today(), count=1)
            if not days:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "JoinQuant returned no recent trading day")
            return FetchResult(records=[{"trading_day": str(days[-1])}], detail="authentication and calendar query succeeded")
        except ProviderError:
            raise
        except Exception as error:
            raise _provider_error(error) from error

    def _probe_health(self) -> Capability:
        try:
            response = self.health_check()
            return _legacy_adapter_capability("health_check", CapabilityStatus.PASS, response.detail, row_count=len(response.records))
        except ProviderError as error:
            return _legacy_adapter_capability("health_check", CapabilityStatus.FAILED, _error_detail(error))

    def _probe_bars(self, capability_name: str, symbol: str, frequency: str) -> Capability:
        try:
            response = self._get_price(symbol, frequency)
            rows = _records(response)
            if not rows:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "provider returned zero rows")
            return _legacy_adapter_capability(
                capability_name,
                CapabilityStatus.PASS,
                f"frequency={frequency}",
                row_count=len(rows),
                earliest=_first_timestamp(response),
                latest=_last_timestamp(response),
            )
        except ProviderError as error:
            return _legacy_adapter_capability(capability_name, CapabilityStatus.FAILED, _error_detail(error))
        except Exception as error:
            return _legacy_adapter_capability(capability_name, CapabilityStatus.FAILED, _error_detail(_provider_error(error)))

    def _discover_current_future(self) -> str | None:
        try:
            securities = self._api().get_all_securities(types=["futures"], date=self._today())
            symbols = _symbols(securities)
            return next((symbol for symbol in symbols if symbol), None)
        except Exception:
            return None

    def _get_price(self, symbol: str, frequency: str) -> Any:
        end = self._today()
        return self._api().get_price(
            symbol,
            start_date=end - timedelta(days=60),
            end_date=end,
            frequency=frequency,
            fields=["open", "close", "high", "low", "volume", "money"],
        )

    def _authenticate(self) -> None:
        if self._authenticated:
            return
        if not self._username or not self._password:
            raise ProviderError(
                ErrorCategory.AUTHENTICATION,
                "JoinQuant credentials are absent; set JQDATA_USERNAME and JQDATA_PASSWORD locally",
            )
        try:
            self._api().auth(self._username, self._password)
            self._authenticated = True
        except Exception as error:
            raise _provider_error(error) from error

    def _api(self) -> Any:
        if self._sdk is not None:
            return self._sdk
        try:
            import jqdatasdk
        except ImportError as error:
            raise ProviderError(ErrorCategory.UNKNOWN, "jqdatasdk is not installed") from error
        self._sdk = jqdatasdk
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
        return [item if isinstance(item, Mapping) else {"value": str(item)} for item in value]
    return [{"value": str(value)}]


def _symbols(value: Any) -> list[str]:
    index = getattr(value, "index", None)
    if index is not None and not callable(index):
        return [str(item) for item in index]
    return [str(item.get("code", "")) if isinstance(item, Mapping) else str(item) for item in _records(value)]


def _first_timestamp(value: Any) -> str | None:
    index = getattr(value, "index", None)
    if index is not None and not callable(index) and len(index):
        return _as_timestamp(index[0])
    return None


def _last_timestamp(value: Any) -> str | None:
    index = getattr(value, "index", None)
    if index is not None and not callable(index) and len(index):
        return _as_timestamp(index[-1])
    return None


def _as_timestamp(value: Any) -> str:
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return f"{text}T00:00:00+08:00" if len(text) == 10 else text


def _provider_error(error: Exception) -> ProviderError:
    text = str(error)
    lowered = text.lower()
    if any(token in lowered for token in ("auth", "password", "username", "login", "permission")):
        category = ErrorCategory.AUTHENTICATION
    elif any(token in lowered for token in ("429", "rate limit", "quota", "too many")):
        category = ErrorCategory.QUOTA
    elif any(
        token in lowered
        for token in ("timeout", "connection", "network", "dns", "socket", "winerror", "网络", "连接", "套接字")
    ):
        category = ErrorCategory.NETWORK
    elif any(token in lowered for token in ("keyerror", "column", "field", "schema")):
        category = ErrorCategory.FIELD_CHANGE
    elif any(token in lowered for token in ("empty", "no data", "not found", "not support")):
        category = ErrorCategory.NO_COVERAGE
    else:
        category = ErrorCategory.UNKNOWN
    return ProviderError(category, text or error.__class__.__name__)


def _error_detail(error: ProviderError) -> str:
    return f"[{error.category.value}] {error.message}"
