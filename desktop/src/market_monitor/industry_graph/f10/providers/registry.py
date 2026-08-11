"""Provider registry used by the enrichment planner and CLI."""

from __future__ import annotations

from .base import F10Provider, ProviderError


def _load_providers() -> dict[str, F10Provider]:
    providers: dict[str, F10Provider] = {}
    from .eastmoney import EastmoneyF10Provider

    providers["eastmoney"] = EastmoneyF10Provider()
    from .tencent import TencentQuoteProvider

    providers["tencent"] = TencentQuoteProvider()
    try:
        from .tdx import TdxF10Provider

        providers["tdx"] = TdxF10Provider()
    except ImportError:
        pass
    try:
        from .ths import ThsF10Provider

        providers["ths"] = ThsF10Provider()
    except ImportError:
        pass
    return providers


_REGISTRY: dict[str, F10Provider] | None = None


def list_providers() -> dict[str, F10Provider]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _load_providers()
    return dict(_REGISTRY)


def get_provider(name: str) -> F10Provider:
    providers = list_providers()
    try:
        return providers[name.strip().lower()]
    except KeyError as error:
        raise ProviderError(f"unknown F10 provider: {name}") from error


def reset_registry() -> None:
    """Testing hook to force a fresh provider load."""
    global _REGISTRY
    _REGISTRY = None


__all__ = ("get_provider", "list_providers", "reset_registry")
