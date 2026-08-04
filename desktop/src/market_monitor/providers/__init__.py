"""Provider contracts and probe orchestration."""

from .base import (
    Capability,
    CapabilityStatus,
    ErrorCategory,
    FetchResult,
    Provider,
    ProviderError,
    ProviderRunResult,
)
from .runner import ProbeRunner, redact_secrets
from .joinquant import JoinQuantProvider
from .baostock import BaostockProvider
from .akshare import AkShareProvider
from .tdx_quant import TdxQuantProvider

__all__ = [
    "Capability",
    "BaostockProvider",
    "AkShareProvider",
    "TdxQuantProvider",
    "CapabilityStatus",
    "ErrorCategory",
    "FetchResult",
    "JoinQuantProvider",
    "ProbeRunner",
    "Provider",
    "ProviderError",
    "ProviderRunResult",
    "redact_secrets",
]
