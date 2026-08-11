"""Unit tests for the F10 provider layer (no network)."""

from __future__ import annotations

import time

import pytest

from market_monitor.f10 import TencentQuote
from market_monitor.industry_graph.f10.providers import (
    CircuitBreaker,
    F10RateLimiter,
    ProviderBlocked,
    ProviderError,
    get_governance,
    governed_get,
    reset_governance,
    validate_max_rps,
)
from market_monitor.industry_graph.f10.providers.eastmoney import EastmoneyF10Provider
from market_monitor.industry_graph.f10.providers.tencent import tencent_quote_fields


def test_max_rps_hard_limit() -> None:
    assert validate_max_rps(4.0) == 4.0
    assert validate_max_rps(10.0) == 10.0
    with pytest.raises(ValueError):
        validate_max_rps(10.01)
    with pytest.raises(ValueError):
        validate_max_rps(0)


def test_rate_limiter_enforces_interval() -> None:
    limiter = F10RateLimiter(max_rps=10.0)
    start = time.monotonic()
    limiter.wait()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.09
    assert limiter.request_count == 2
    assert limiter.stats()["maxRps"] == 10.0


def test_circuit_breaker_opens_and_recovers() -> None:
    breaker = CircuitBreaker(name="test", failure_threshold=3, reset_after_seconds=0.05)
    assert breaker.allow()
    assert breaker.record_failure("bad") is False
    assert breaker.record_failure("bad") is False
    assert breaker.record_failure("bad") is True
    assert not breaker.allow()
    assert breaker.failures == 3
    breaker.record_blocked("403")
    assert breaker.blocked == 1
    breaker.record_success()
    assert breaker.allow()
    assert breaker.successes == 1
    assert breaker.consecutive_failures == 0


def test_governed_get_uses_limiter_and_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_governance()
    governance = get_governance(max_rps=10.0)
    calls: list[str] = []

    def fake_get(url: str, *, timeout: float, encoding: str, headers=None) -> str:
        calls.append(url)
        raise RuntimeError("boom")

    monkeypatch.setattr("market_monitor.f10._get", fake_get)
    with pytest.raises(ProviderError):
        governed_get("https://example.test", provider="test", governance=governance, attempts=2, backoff_base_seconds=0.001)
    assert len(calls) == 2
    assert governance.breaker("test").consecutive_failures == 2


def test_governed_get_raises_blocked_when_breaker_open() -> None:
    governance = get_governance(max_rps=10.0)
    governance.breaker("blocked").record_failure("x")
    governance.breaker("blocked").record_failure("x")
    governance.breaker("blocked").record_failure("x")
    governance.breaker("blocked").record_failure("x")
    governance.breaker("blocked").record_failure("x")
    with pytest.raises(ProviderBlocked):
        governed_get("https://example.test", provider="blocked", governance=governance)
    assert governance.breaker("blocked").blocked == 1


def test_tencent_quote_fields_conversion() -> None:
    quote = TencentQuote(
        symbol="hk02513",
        name="TENCENT",
        code="02513",
        price=100.5,
        prev_close=99.0,
        change_pct=1.5,
        total_market_cap_yi=4000.0,
        float_market_cap_yi=3900.0,
        pe=20.0,
        pb=3.0,
        high=101.0,
        low=99.0,
        turnover_rate=0.5,
        volume_ratio=1.1,
        amount_yi=12.0,
        quote_time="2026/08/09 10:00:00",
    )
    fields = tencent_quote_fields(vars(quote), market="HK")
    assert fields["total_market_cap"] == {
        "value": 400_000_000_000.0,
        "currency": "HKD",
        "asOf": "2026/08/09 10:00:00",
        "source": "tencent_quote",
        "derived": False,
    }
    assert fields["float_market_cap"]["value"] == 390_000_000_000.0
    assert fields["price"] == 100.5


def test_eastmoney_provider_adapts_existing_records(monkeypatch: pytest.MonkeyPatch) -> None:
    import market_monitor.f10 as f10_module

    def fake_survey(code: str, *, market: str = "CN", quote=None) -> dict:
        return {
            "code": code,
            "name": "Example Co",
            "org_name": "Example Co Ltd",
            "org_web": "https://example.test",
            "org_profile": "A real profile.",
            "business_scope": "Software",
            "industry_em": "Software",
            "industry_csrc": "Manufacturing",
        }

    def fake_business(code: str) -> dict:
        return {
            "code": code,
            "revenue_breakdown": [
                {
                    "item": "Cloud",
                    "income": 100.0,
                    "ratio": 0.5,
                    "period": "2025-12-31",
                    "type": "2",
                    "classification": "product",
                    "classification_label": "产品",
                    "source": "eastmoney_f10",
                }
            ],
            "fetched_at": "2026-08-09T00:00:00+00:00",
        }

    monkeypatch.setattr(f10_module, "fetch_company_survey", fake_survey)
    monkeypatch.setattr(f10_module, "fetch_business_analysis", fake_business)
    provider = EastmoneyF10Provider()
    profile = provider.fetch_profile("688825")
    assert profile.fields["name"] == "Example Co"
    assert profile.fields["company_intro"] == "A real profile."
    assert profile.fields["business_scope"] == "Software"
    assert profile.provenance["company_website"]["source"] == "eastmoney"
    revenue = provider.fetch_revenue("688825")
    assert revenue.revenue_breakdown[0]["item"] == "Cloud"
    assert revenue.revenue_breakdown[0]["period"] == "2025-12-31"


def test_eastmoney_revenue_hk_unsupported() -> None:
    provider = EastmoneyF10Provider()
    with pytest.raises(ProviderError):
        provider.fetch_revenue("02513", market="HK")
