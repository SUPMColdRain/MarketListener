"""Only concrete, real source implementations are registered here."""

from __future__ import annotations

from .base import Provider
from .akshare import AkShareProvider
from .baostock import BaostockProvider
from .joinquant import JoinQuantProvider
from .tdx_quant import TdxQuantProvider


def registered_providers() -> tuple[Provider, ...]:
    return (JoinQuantProvider(), BaostockProvider(), AkShareProvider(), TdxQuantProvider())
