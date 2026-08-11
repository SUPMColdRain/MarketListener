"""Multi-source F10 providers (Eastmoney / TDX / THS / Tencent)."""

from __future__ import annotations

from .base import (
    F10Provider,
    ProviderBlocked,
    ProviderCapabilities,
    ProviderError,
    ProviderPage,
    ProviderResult,
)
from .governance import (
    CircuitBreaker,
    DEFAULT_MAX_RPS,
    F10Governance,
    F10RateLimiter,
    HARD_MAX_RPS,
    get_governance,
    governed_get,
    reset_governance,
    validate_max_rps,
)
from .registry import get_provider, list_providers, reset_registry
from .eastmoney import EastmoneyF10Provider
from .tdx import TdxF10Provider
from .ths import ThsF10Provider
from .tencent import TencentQuoteProvider

__all__ = (
    "CircuitBreaker",
    "DEFAULT_MAX_RPS",
    "EastmoneyF10Provider",
    "F10Governance",
    "F10Provider",
    "F10RateLimiter",
    "HARD_MAX_RPS",
    "ProviderBlocked",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderPage",
    "ProviderResult",
    "TdxF10Provider",
    "ThsF10Provider",
    "TencentQuoteProvider",
    "get_governance",
    "get_provider",
    "governed_get",
    "list_providers",
    "reset_governance",
    "reset_registry",
    "validate_max_rps",
)
