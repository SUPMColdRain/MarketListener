"""Real Tushare capability probe with per-interface permission and coverage reporting."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Callable, Mapping, Sequence

from .base import (
    AssetType,
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    ConfigurationRequirement,
    ErrorCategory,
    FetchResult,
    Market,
    Provider,
    ProviderError,
    ProviderOperation,
    ProviderRequest,
    SourceDescription,
)


class TushareProvider(Provider):
    name = "tushare"
    source_description = SourceDescription(
        "tushare",
        "Tushare",
        "Token-gated China-market data interface adapter",
        website="https://tushare.pro",
    )
    _stock = "600519.SH"

    def __init__(
        self,
        *,
        sdk: Any | None = None,
        token: str | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._sdk = sdk
        self._token = token if token is not None else os.getenv("TUSHARE_TOKEN")
        self._today = today
        self._pro: Any | None = None

    def configuration_requirements(self) -> Sequence[ConfigurationRequirement]:
        return (
            ConfigurationRequirement(
                "TUSHARE_TOKEN",
                "configuration-tushare-token",
                "Local Tushare token is required before token-gated probes",
            ),
        )

    def configure(self, values: Mapping[str, str]) -> None:
        if self._token is None:
            self._token = values.get("TUSHARE_TOKEN")

    def missing_configuration_requirements(self) -> Sequence[ConfigurationRequirement]:
        return tuple(
            requirement
            for requirement in self.configuration_requirements()
            if not self._token
        )

    def probe_capabilities(self) -> Sequence[Capability]:
        api = self._api()
        return (
            self._probe_calendar(api),
            self._probe_daily(api),
            self._probe_stock_basic(api),
            self._probe_financial(api),
            self._probe_minute(api),
            self._probe_account(api),
        )

    def fetch_instruments(self) -> FetchResult:
        records = _records(self._api().stock_basic(exchange="", list_status="L"))
        return FetchResult(records=records, detail="Tushare listed A-share catalogue")

    def fetch_bars(self) -> FetchResult:
        start, end = _date_range(self._today())
        records = _records(
            self._api().daily(ts_code=self._stock, start_date=start, end_date=end)
        )
        return FetchResult(
            records=records,
            earliest=_earliest(records),
            latest=_latest(records),
            detail=f"Tushare {self._stock} daily bars",
        )

    def fetch_indicators(self) -> FetchResult:
        start, end = _date_range(self._today())
        records = _records(
            self._api().income(ts_code=self._stock, start_date=start, end_date=end)
        )
        return FetchResult(records=records, detail=f"Tushare {self._stock} financial reports")

    def fetch_calendar(self) -> FetchResult:
        start, end = _date_range(self._today())
        records = _records(
            self._api().trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1")
        )
        return FetchResult(records=records, detail="Tushare SSE trading calendar")

    def health_check(self) -> FetchResult:
        calendar = self.fetch_calendar()
        if not calendar.records:
            raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare returned no calendar rows")
        return FetchResult(records=calendar.records[-1:], detail="token and calendar query succeeded")

    def _probe_calendar(self, api: Any) -> Capability:
        registration = CapabilityRegistration(
            "tushare-calendar",
            "Tushare SSE trading calendar",
            ProviderRequest(ProviderOperation.CALENDAR, market=Market.CN),
        )
        try:
            start, end = _date_range(self._today())
            records = _records(api.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1"))
            if not records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare returned zero calendar rows")
            return _capability(
                registration,
                CapabilityStatus.PASS,
                detail="exchange=SSE",
                row_count=len(records),
                earliest=_earliest(records, "cal_date"),
                latest=_latest(records, "cal_date"),
            )
        except ProviderError as error:
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(error), error=error)
        except Exception as error:
            wrapped = _provider_error(error)
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(wrapped), error=wrapped)

    def _probe_daily(self, api: Any) -> Capability:
        start, end = _date_range(self._today())
        registration = CapabilityRegistration(
            "tushare-daily",
            "Tushare A-share daily bars",
            ProviderRequest(
                ProviderOperation.BARS,
                Market.CN,
                AssetType.STOCK,
                period="1d",
                start_date=_iso_start(start),
                end_date=_iso_start(end),
                instrument=self._stock,
            ),
        )
        try:
            records = _records(api.daily(ts_code=self._stock, start_date=start, end_date=end))
            if not records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare returned zero daily rows")
            return _capability(
                registration,
                CapabilityStatus.PASS,
                detail=f"ts_code={self._stock}; period=1d",
                row_count=len(records),
                earliest=_earliest(records),
                latest=_latest(records),
            )
        except ProviderError as error:
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(error), error=error)
        except Exception as error:
            wrapped = _provider_error(error)
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(wrapped), error=wrapped)

    def _probe_stock_basic(self, api: Any) -> Capability:
        registration = CapabilityRegistration(
            "tushare-stock-basic",
            "Tushare listed A-share basic profile catalogue",
            ProviderRequest(ProviderOperation.INSTRUMENTS, market=Market.CN),
        )
        try:
            records = _records(api.stock_basic(exchange="", list_status="L"))
            if not records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare returned zero stock-basic rows")
            return _capability(
                registration,
                CapabilityStatus.PASS,
                detail="list_status=L",
                row_count=len(records),
            )
        except ProviderError as error:
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(error), error=error)
        except Exception as error:
            wrapped = _provider_error(error)
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(wrapped), error=wrapped)

    def _probe_financial(self, api: Any) -> Capability:
        start, end = _date_range(self._today())
        registration = CapabilityRegistration(
            "tushare-financial",
            "Tushare A-share income statement coverage",
            ProviderRequest(
                ProviderOperation.INDICATORS,
                Market.CN,
                AssetType.STOCK,
                start_date=_iso_start(start),
                end_date=_iso_start(end),
                instrument=self._stock,
            ),
        )
        try:
            records = _records(api.income(ts_code=self._stock, start_date=start, end_date=end))
            if not records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare returned zero income rows")
            return _capability(
                registration,
                CapabilityStatus.PASS,
                detail=f"ts_code={self._stock}; report=income",
                row_count=len(records),
                earliest=_earliest(records, "end_date"),
                latest=_latest(records, "end_date"),
            )
        except ProviderError as error:
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(error), error=error)
        except Exception as error:
            wrapped = _provider_error(error)
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(wrapped), error=wrapped)

    def _probe_minute(self, api: Any) -> Capability:
        start, end = _date_range(self._today())
        registration = CapabilityRegistration(
            "tushare-minute",
            "Tushare A-share one-minute bars",
            ProviderRequest(
                ProviderOperation.BARS,
                Market.CN,
                AssetType.STOCK,
                period="1m",
                start_date=_iso_start(start),
                end_date=_iso_start(end),
                instrument=self._stock,
            ),
        )
        try:
            records = _records(
                api.stk_mins(
                    ts_code=self._stock,
                    freq="1min",
                    start_date=f"{start} 09:30:00",
                    end_date=f"{end} 15:00:00",
                )
            )
            if not records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare returned zero minute rows")
            return _capability(
                registration,
                CapabilityStatus.PASS,
                detail=f"ts_code={self._stock}; freq=1min",
                row_count=len(records),
                earliest=_earliest(records, "trade_time"),
                latest=_latest(records, "trade_time"),
            )
        except ProviderError as error:
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(error), error=error)
        except Exception as error:
            wrapped = _provider_error(error)
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(wrapped), error=wrapped)

    def _probe_account(self, api: Any) -> Capability:
        registration = CapabilityRegistration(
            "tushare-account",
            "Tushare account points and interface entitlement",
            ProviderRequest(ProviderOperation.OTHER),
        )
        try:
            records = _records(api.user(token=self._token))
            if not records:
                raise ProviderError(ErrorCategory.NO_COVERAGE, "Tushare user API returned zero rows")
            points = records[0].get("point")
            detail = f"points={points}" if points is not None else "points field absent"
            return _capability(registration, CapabilityStatus.PASS, detail=detail, row_count=len(records))
        except ProviderError as error:
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(error), error=error)
        except Exception as error:
            wrapped = _provider_error(error)
            return _capability(registration, CapabilityStatus.FAILED, detail=_error_detail(wrapped), error=wrapped)

    def _api(self) -> Any:
        if self._pro is not None:
            return self._pro
        if not self._token:
            raise ProviderError(
                ErrorCategory.CONFIGURATION,
                "Tushare token is absent; set TUSHARE_TOKEN locally",
            )
        if self._sdk is not None:
            try:
                set_token = getattr(self._sdk, "set_token", None)
                if set_token is not None:
                    set_token(self._token)
                self._pro = self._sdk.pro_api()
            except Exception as error:
                raise _provider_error(error) from error
            return self._pro
        try:
            import tushare
        except ImportError as error:
            raise ProviderError(ErrorCategory.UNKNOWN, "tushare is not installed") from error
        try:
            tushare.set_token(self._token)
            self._pro = tushare.pro_api()
        except Exception as error:
            raise _provider_error(error) from error
        return self._pro


def _capability(
    registration: CapabilityRegistration,
    status: CapabilityStatus,
    *,
    detail: str | None = None,
    row_count: int | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    error: ProviderError | None = None,
) -> Capability:
    return Capability(
        registration.id,
        status,
        detail,
        row_count,
        earliest,
        latest,
        registration=registration,
        error=error,
    )


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


def _date_range(today: date) -> tuple[str, str]:
    start = today - timedelta(days=60)
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def _iso_start(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def _earliest(records: Sequence[Mapping[str, Any]], field: str = "trade_date") -> str | None:
    values = _date_values(records, field)
    return _iso_datetime(min(values)) if values else None


def _latest(records: Sequence[Mapping[str, Any]], field: str = "trade_date") -> str | None:
    values = _date_values(records, field)
    return _iso_datetime(max(values)) if values else None


def _date_values(records: Sequence[Mapping[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for record in records:
        value = record.get(field)
        if value is None:
            continue
        text = str(value)
        if text and text != "nan":
            values.append("".join(character for character in text if character.isdigit())[:14])
    return values


def _iso_datetime(value: str) -> str:
    if len(value) >= 8 and value[:8].isdigit():
        day = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        time = value[8:14]
        if len(time) == 6 and time.isdigit():
            return f"{day}T{time[:2]}:{time[2:4]}:{time[4:6]}+08:00"
        return f"{day}T00:00:00+08:00"
    return value


def _provider_error(error: Exception) -> ProviderError:
    text = str(error)
    lowered = text.lower()
    if any(token in lowered for token in ("token", "invalid", "认证", "鉴权")):
        category = ErrorCategory.AUTHENTICATION
    elif any(token in lowered for token in ("没有访问", "无权限", "permission", "forbidden", "not authorized")):
        category = ErrorCategory.NO_COVERAGE
    elif any(token in lowered for token in ("积分", "频次", "频率", "每分钟", "rate limit", "quota", "次数")):
        category = ErrorCategory.QUOTA
    elif any(
        token in lowered
        for token in ("timeout", "connection", "network", "dns", "socket", "winerror", "网络", "连接", "系统繁忙", "重试")
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
