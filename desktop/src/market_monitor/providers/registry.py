"""Provider and capability registration with no source-wide support inference."""

from __future__ import annotations

from typing import Mapping

from .base import CapabilityRegistration, Provider, ProviderRequest
from .akshare import AkShareProvider
from .baostock import BaostockProvider
from .joinquant import JoinQuantProvider
from .pytdx import TdxProvider
from .tdx_quant import TdxQuantProvider
from .tushare import TushareProvider


def registered_providers(configuration: Mapping[str, str] | None = None) -> tuple[Provider, ...]:
    providers: tuple[Provider, ...] = (
        JoinQuantProvider(),
        BaostockProvider(),
        AkShareProvider(),
        TdxProvider(),
        TushareProvider(),
        TdxQuantProvider(),
    )
    if configuration is not None:
        for provider in providers:
            provider.configure(configuration)
    return providers


class CapabilityRegistry:
    """A strict registry used by future routing code to reject undeclared needs."""

    def __init__(self, registrations: tuple[CapabilityRegistration, ...] = ()) -> None:
        self._registrations: dict[str, CapabilityRegistration] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: CapabilityRegistration) -> None:
        if registration.id in self._registrations:
            raise ValueError(f"duplicate capability registration: {registration.id}")
        self._registrations[registration.id] = registration

    def require(self, capability_id: str, request: ProviderRequest) -> CapabilityRegistration:
        registration = self._registrations.get(capability_id)
        if registration is None:
            raise ValueError(f"unknown capability: {capability_id}")
        if registration.request != request:
            raise ValueError(f"request does not match capability registration: {capability_id}")
        return registration

    def all(self) -> tuple[CapabilityRegistration, ...]:
        return tuple(self._registrations.values())
