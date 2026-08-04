"""Fixed provider responses exercise D0-010 failure isolation."""

from __future__ import annotations

import json
from threading import Event
from time import monotonic

import pytest

from market_monitor.contracts import validate_contract
from market_monitor.providers import (
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    ErrorCategory,
    FetchResult,
    ProbeRunner,
    Provider,
    ProviderError,
    ProviderOperation,
    ProviderRequest,
    redact_secrets,
)


class StaticProvider(Provider):
    def __init__(self, name: str, response: object) -> None:
        self.name = name
        self.response = response

    def probe_capabilities(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def fetch_instruments(self) -> FetchResult:
        return FetchResult(records=[])

    def fetch_bars(self) -> FetchResult:
        return FetchResult(records=[])

    def fetch_indicators(self) -> FetchResult:
        return FetchResult(records=[])

    def fetch_calendar(self) -> FetchResult:
        return FetchResult(records=[])

    def health_check(self) -> FetchResult:
        return FetchResult(records=[])


class BlockingProvider(StaticProvider):
    def __init__(self, name: str) -> None:
        super().__init__(name, [])
        self.release = Event()

    def probe_capabilities(self):
        self.release.wait()
        return []


def _static_capability(name: str, status: CapabilityStatus, detail: str | None = None, row_count: int | None = None) -> Capability:
    return Capability(
        name,
        status,
        detail,
        row_count,
        registration=CapabilityRegistration(
            name, f"Static test capability: {name}", ProviderRequest(ProviderOperation.OTHER)
        ),
    )


@pytest.mark.parametrize(
    ("response", "expected_status", "expected_category"),
    [
        ([_static_capability("normal", CapabilityStatus.PASS, row_count=2)], "PASS", None),
        (ProviderError(ErrorCategory.NO_COVERAGE, "empty response"), "FAILED", "NO_COVERAGE"),
        (ProviderError(ErrorCategory.NETWORK, "request timeout"), "FAILED", "NETWORK"),
        (ProviderError(ErrorCategory.QUOTA, "HTTP 429"), "FAILED", "RATE_LIMIT"),
        (ProviderError(ErrorCategory.FIELD_CHANGE, "required close field missing"), "FAILED", "PROVIDER"),
        (
            [
                _static_capability("partial", CapabilityStatus.PASS, row_count=1),
                _static_capability("missing", CapabilityStatus.FAILED, "field absent"),
            ],
            "FAILED",
            None,
        ),
    ],
)
def test_fixed_provider_responses_are_classified(
    response: object,
    expected_status: str,
    expected_category: str | None,
) -> None:
    result = ProbeRunner().run([StaticProvider("fixed", response)]).results[0]
    assert result.capabilities[-1].status.value == expected_status
    assert (result.capabilities[-1].error.category.value if result.capabilities[-1].error else None) == expected_category


def test_failure_does_not_stop_later_provider_and_reports_are_dual_format(tmp_path) -> None:
    report = ProbeRunner().run(
        [
            StaticProvider("broken", ProviderError(ErrorCategory.NETWORK, "token=secret-value")),
            StaticProvider("healthy", [_static_capability("bars", CapabilityStatus.PASS, row_count=2)]),
        ]
    )
    machine_path, human_path = ProbeRunner().write_reports(report, tmp_path)

    payload = json.loads(machine_path.read_text(encoding="utf-8"))
    assert [item["source"]["id"] for item in payload["providers"]] == ["broken", "healthy"]
    assert payload["providers"][0]["capabilities"][0]["error"]["message"] == "token=***"
    assert "healthy" in human_path.read_text(encoding="utf-8")


def test_timeout_is_reported_and_does_not_stop_later_provider() -> None:
    blocking = BlockingProvider("blocked-network")
    started = monotonic()
    try:
        report = ProbeRunner(timeout_seconds=0.01).run(
            [blocking, StaticProvider("healthy", [_static_capability("bars", CapabilityStatus.PASS, row_count=2)])]
        )
    finally:
        blocking.release.set()

    assert monotonic() - started < 1
    assert [result.capabilities[-1].status for result in report.results] == [CapabilityStatus.FAILED, CapabilityStatus.PASS]
    assert report.results[0].capabilities[0].error == ProviderError(ErrorCategory.NETWORK, "provider probe exceeded 0.01 seconds")


def test_secret_redaction_covers_common_error_shapes() -> None:
    assert redact_secrets("account=alice token=abc Bearer xyz") == "account=*** token=*** Bearer ***"


def test_run_result_matches_the_shared_contract() -> None:
    result = ProbeRunner().run(
        [StaticProvider("healthy", [_static_capability("bars", CapabilityStatus.PASS, row_count=2)])]
    ).results[0]
    validate_contract("provider-run-result.schema.json", result.to_dict())
