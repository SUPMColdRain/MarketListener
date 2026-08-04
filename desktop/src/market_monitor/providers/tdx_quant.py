"""Evidence-based unsupported state for the requested tdx_quant package."""

from __future__ import annotations

import importlib.util
from typing import Sequence

from .base import Capability, CapabilityStatus, ErrorCategory, FetchResult, Provider, ProviderError


class TdxQuantProvider(Provider):
    name = "tdx_quant"
    _gap = "tdx_quant package/API is not verifiably installed; HK stocks, index and futures coverage unavailable"

    def probe_capabilities(self) -> Sequence[Capability]:
        if importlib.util.find_spec("tdx_quant") is None:
            return (
                Capability("package_installation", CapabilityStatus.UNSUPPORTED, self._gap),
                Capability("license_and_maintenance", CapabilityStatus.UNSUPPORTED, "No verifiable package source to inspect"),
                Capability("callable_api", CapabilityStatus.UNSUPPORTED, "No importable tdx_quant module"),
                Capability("hk_stock_index_future", CapabilityStatus.UNSUPPORTED, self._gap),
            )
        return (
            Capability(
                "callable_api",
                CapabilityStatus.UNSUPPORTED,
                "tdx_quant is importable but no approved API adapter has been verified",
            ),
        )

    def fetch_instruments(self) -> FetchResult:
        raise ProviderError(ErrorCategory.NO_COVERAGE, self._gap)

    def fetch_bars(self) -> FetchResult:
        raise ProviderError(ErrorCategory.NO_COVERAGE, self._gap)

    def fetch_indicators(self) -> FetchResult:
        raise ProviderError(ErrorCategory.NO_COVERAGE, self._gap)

    def fetch_calendar(self) -> FetchResult:
        raise ProviderError(ErrorCategory.NO_COVERAGE, self._gap)

    def health_check(self) -> FetchResult:
        raise ProviderError(ErrorCategory.NO_COVERAGE, self._gap)
