"""Provider Contract v2 model, registry, schema, and migration coverage."""

from __future__ import annotations

from copy import deepcopy
import json
import re
import subprocess
import sys

import pytest

import market_monitor.providers as providers
from market_monitor.contracts import ContractValidationError, validate_contract
from market_monitor.providers import (
    AssetType,
    Capability,
    CapabilityEvidence,
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityStatus,
    ErrorCategory,
    Market,
    ProviderError,
    ProviderOperation,
    ProviderRequest,
    ProviderRunResult,
    SourceDescription,
    migrate_v1_provider_run_result,
)


def _registration() -> CapabilityRegistration:
    return CapabilityRegistration(
        "cn-stock-daily-bars",
        "A-share daily history",
        ProviderRequest(
            ProviderOperation.BARS,
            Market.CN,
            AssetType.STOCK,
            period="1d",
            start_date="2026-08-01",
            end_date="2026-08-05",
            instrument="CN-SSE-STOCK-600519",
        ),
        ("historical-bars",),
    )


def _result() -> ProviderRunResult:
    return ProviderRunResult(
        "probe-contract-v2",
        SourceDescription("fixture-provider", "Fixture Provider", "Fixed test source"),
        "2026-08-05T00:00:00+00:00",
        "2026-08-05T00:00:01+00:00",
        (
            Capability(
                "cn-stock-daily-bars",
                CapabilityStatus.PASS,
                registration=_registration(),
                probed_at="2026-08-05T00:00:01+00:00",
                evidence=CapabilityEvidence("five rows", row_count=5),
            ),
        ),
    )


def _v1_result() -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": "v1-run",
        "provider": "legacy_provider",
        "status": "FAILED",
        "started_at": "2026-08-05T00:00:00+00:00",
        "completed_at": "2026-08-05T00:00:01+00:00",
        "capabilities": [
            {"name": "vendor-only-thing", "status": "UNSUPPORTED", "detail": "not documented"}
        ],
        "error": {"category": "NETWORK", "message": "connection closed"},
    }


def test_model_json_schema_round_trip_is_v2_strict() -> None:
    document = _result().to_dict()

    validate_contract("provider-run-result.schema.json", document)
    assert document["schema_version"] == 2
    assert "status" not in document
    assert document["capabilities"][0]["registration"]["request"]["period"] == "1d"


def test_v1_migration_preserves_legacy_status_unknown_capability_and_run_error() -> None:
    migrated = migrate_v1_provider_run_result(_v1_result())

    document = migrated.to_dict()
    validate_contract("provider-run-result.schema.json", document)
    assert document["migration"] == {"from_schema_version": 1, "legacy_provider_status": "FAILED"}
    assert document["capabilities"][0]["registration"]["request"]["operation"] == "other"
    assert document["capabilities"][1]["error"] == {"category": "NETWORK", "message": "connection closed"}


@pytest.mark.parametrize(
    ("mutate", "has_root_error", "capability_count"),
    [
        (lambda document: document, True, 2),
        (lambda document: document.pop("error"), False, 1),
        (
            lambda document: (document.pop("error"), document.update({"capabilities": []})),
            False,
            0,
        ),
    ],
)
def test_v1_migration_cross_field_shapes_round_trip(
    mutate, has_root_error: bool, capability_count: int
) -> None:
    document = _v1_result()
    mutate(document)

    migrated = migrate_v1_provider_run_result(document)
    payload = migrated.to_dict()
    validate_contract("provider-run-result.schema.json", payload)
    assert payload == migrated.to_dict()
    assert payload["source"]["legacy_name"] == "legacy_provider"
    assert len(payload["capabilities"]) == capability_count
    assert any(
        item["registration"]["id"].startswith("migration-root-error-")
        for item in payload["capabilities"]
    ) is has_root_error


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.pop("migration"),
        lambda document: document["source"].pop("legacy_name"),
        lambda document: (
            document["capabilities"][0]["registration"].pop("legacy_name"),
            document["capabilities"][0]["registration"].pop("legacy_occurrence"),
        ),
    ],
)
def test_v2_schema_rejects_forged_or_incomplete_migration_identity(mutate) -> None:
    document = migrate_v1_provider_run_result(_v1_result()).to_dict()
    mutate(document)

    with pytest.raises(ContractValidationError):
        validate_contract("provider-run-result.schema.json", document)


def test_provider_run_result_rejects_cross_field_migration_spoofing() -> None:
    normal_source = SourceDescription("fixture-provider", "Fixture Provider", "Fixed test source")
    migrated_source = SourceDescription(
        "legacy-provider", "Migrated Provider", "Migrated source", legacy_name="legacy_provider"
    )
    migration = {"from_schema_version": 1, "legacy_provider_status": "FAILED"}
    migrated_registration = CapabilityRegistration(
        "legacy-capability",
        "Migrated legacy capability",
        ProviderRequest(ProviderOperation.OTHER),
        legacy_name="legacy_capability",
        legacy_occurrence=0,
    )
    migrated_capability = Capability(
        "legacy-capability", CapabilityStatus.PASS, registration=migrated_registration
    )
    malformed_root = Capability(
        "migration-root-error-fake",
        CapabilityStatus.FAILED,
        registration=CapabilityRegistration(
            "migration-root-error-fake",
            "Migrated v1 root-level error",
            ProviderRequest(ProviderOperation.OTHER),
        ),
    )

    with pytest.raises(ValueError, match="ordinary v2"):
        ProviderRunResult(
            "normal-spoof", normal_source, "2026-08-05T00:00:00+00:00",
            "2026-08-05T00:00:01+00:00", (migrated_capability,)
        )
    with pytest.raises(ValueError, match="legacy source"):
        ProviderRunResult(
            "migration-spoof", normal_source, "2026-08-05T00:00:00+00:00",
            "2026-08-05T00:00:01+00:00", (), migration=migration
        )
    with pytest.raises(ValueError, match="only migrated capabilities"):
        ProviderRunResult(
            "migration-spoof", migrated_source, "2026-08-05T00:00:00+00:00",
            "2026-08-05T00:00:01+00:00", (_result().capabilities[0],), migration=migration
        )
    with pytest.raises(ValueError, match="failed synthetic"):
        ProviderRunResult(
            "migration-spoof", migrated_source, "2026-08-05T00:00:00+00:00",
            "2026-08-05T00:00:01+00:00", (malformed_root,), migration=migration
        )


def test_v1_and_v2_provider_schemas_are_explicitly_routed() -> None:
    validate_contract("provider-run-result-v1.schema.json", _v1_result())
    with pytest.raises(ContractValidationError):
        validate_contract("provider-run-result.schema.json", _v1_result())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update({"future_v1_field": {"must_not": "be_dropped"}}),
        lambda document: document["error"].update({"future_error_field": "must_not_be_dropped"}),
        lambda document: document["capabilities"][0].update({"future_capability_field": True}),
        lambda document: document.update({"status": "BLOCKED"}),
        lambda document: document["capabilities"][0].update({"row_count": -1}),
        lambda document: document.update({"started_at": "not-a-date-time"}),
    ],
)
def test_v1_migration_rejects_every_unrepresentable_or_invalid_input_field(mutate) -> None:
    document = _v1_result()
    mutate(document)

    with pytest.raises(ValueError, match="invalid v1 Provider report"):
        migrate_v1_provider_run_result(document)


def test_v1_legal_identifier_edge_cases_migrate_losslessly_to_unique_v2_ids() -> None:
    document = _v1_result()
    document["provider"] = "123-source"
    document["capabilities"] = [
        {"name": "123-unknown", "status": "UNSUPPORTED"},
        {"name": "foo bar", "status": "PASS"},
        {"name": "foo-bar", "status": "PASS"},
        {"name": "foo bar", "status": "PASS"},
        {"name": "中文能力", "status": "UNSUPPORTED"},
        {"name": "cn_stock_600519.XSHG_1d", "status": "PASS"},
        {"name": "provider-run-error", "status": "FAILED"},
    ]

    migrated = migrate_v1_provider_run_result(document)
    repeated = migrate_v1_provider_run_result(document)
    payload = migrated.to_dict()
    registrations = [item["registration"] for item in payload["capabilities"]]
    identifiers = [registration["id"] for registration in registrations]

    validate_contract("provider-run-result.schema.json", payload)
    assert payload == repeated.to_dict()
    assert payload["source"]["display_name"] == "123-source"
    assert payload["source"]["legacy_name"] == "123-source"
    assert re.fullmatch(r"[a-z][a-z0-9-]{0,63}", payload["source"]["id"])
    assert len(identifiers) == len(set(identifiers))
    assert all(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", identifier) for identifier in identifiers)
    assert any(registration["request"]["operation"] == "bars" for registration in registrations)
    for legacy_name, registration in zip(
        ["123-unknown", "foo bar", "foo-bar", "foo bar", "中文能力", "cn_stock_600519.XSHG_1d", "provider-run-error"],
        registrations,
        strict=False,
    ):
        assert legacy_name in registration["description"]
        assert registration["legacy_name"] == legacy_name
    assert payload["capabilities"][-1]["registration"]["id"].startswith("migration-root-error-")


def test_v1_technical_ids_are_order_independent_and_preserve_blank_raw_names(tmp_path) -> None:
    names = ["foo bar", "foo-bar", "foo bar", "中文能力", " "]
    first = _v1_result()
    first["provider"] = " "
    first["capabilities"] = [{"name": name, "status": "PASS"} for name in names]
    second = deepcopy(first)
    second["capabilities"] = list(reversed(second["capabilities"]))

    first_payload = migrate_v1_provider_run_result(first).to_dict()
    second_payload = migrate_v1_provider_run_result(second).to_dict()
    validate_contract("provider-run-result.schema.json", first_payload)
    validate_contract("provider-run-result.schema.json", second_payload)
    assert first_payload["source"]["legacy_name"] == " "
    assert first_payload["source"]["display_name"] != " "
    assert _legacy_id_map(first_payload) == _legacy_id_map(second_payload)
    assert {name for name, _ in _legacy_id_map(first_payload)} == set(names)

    script = """
import json
import sys
from market_monitor.providers import migrate_v1_provider_run_result
payload = migrate_v1_provider_run_result(json.load(sys.stdin)).to_dict()
rows = [
    (item['registration']['legacy_name'], item['registration']['legacy_occurrence'], item['registration']['id'])
    for item in payload['capabilities'] if 'legacy_name' in item['registration']
]
print(json.dumps(sorted(rows), ensure_ascii=False))
"""
    first_process = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(first), text=True,
        capture_output=True, check=True, cwd=tmp_path
    )
    second_process = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(first), text=True,
        capture_output=True, check=True, cwd=tmp_path
    )
    assert first_process.stdout == second_process.stdout


def _legacy_id_map(payload: dict[str, object]) -> dict[tuple[str, int], str]:
    return {
        (str(registration["legacy_name"]), int(registration["legacy_occurrence"])): str(registration["id"])
        for item in payload["capabilities"]
        if "legacy_name" in (registration := item["registration"])
    }


def test_unknown_capability_and_request_mismatch_are_rejected() -> None:
    registry = CapabilityRegistry((_registration(),))

    with pytest.raises(ValueError, match="unknown capability"):
        registry.require("does-not-exist", _registration().request)
    with pytest.raises(ValueError, match="does not match"):
        registry.require(
            "cn-stock-daily-bars",
            ProviderRequest(ProviderOperation.BARS, Market.CN, AssetType.STOCK, period="30m"),
        )


@pytest.mark.parametrize(
    "request_kwargs",
    [
        {"operation": ProviderOperation.BARS, "market": Market.CN, "asset_type": AssetType.STOCK},
        {"operation": ProviderOperation.BARS, "market": Market.GLOBAL, "asset_type": AssetType.STOCK, "period": "1d"},
        {"operation": ProviderOperation.CALENDAR, "market": Market.CN, "asset_type": AssetType.STOCK},
        {"operation": ProviderOperation.HEALTH_CHECK, "period": "1d"},
        {"operation": ProviderOperation.BARS, "market": Market.CN, "asset_type": AssetType.STOCK, "period": "1d", "start_date": "2026-08-05"},
        {"operation": ProviderOperation.CALENDAR, "period": ""},
        {"operation": ProviderOperation.HEALTH_CHECK, "instrument": "   "},
        {"operation": ProviderOperation.INSTRUMENTS, "start_date": "", "end_date": ""},
        {"operation": ProviderOperation.INDICATORS, "parameters": {"": "value"}},
        {"operation": ProviderOperation.INDICATORS, "parameters": {"kind": "   "}},
    ],
)
def test_illegal_request_combinations_are_rejected(request_kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ProviderRequest(**request_kwargs)


def test_illegal_status_combinations_are_rejected_by_model_and_schema() -> None:
    with pytest.raises(ValueError, match="PASS capability"):
        Capability(
            "cn-stock-daily-bars",
            CapabilityStatus.PASS,
            registration=_registration(),
            error=ProviderError(ErrorCategory.NETWORK, "network unavailable"),
        )
    with pytest.raises(ValueError, match="explicit registration"):
        Capability("unregistered-v2-capability", CapabilityStatus.UNSUPPORTED)
    with pytest.raises(ValueError, match="BLOCKED capability"):
        Capability("cn-stock-daily-bars", CapabilityStatus.BLOCKED, registration=_registration())

    document = _result().to_dict()
    malformed = deepcopy(document)
    malformed["capabilities"][0]["status"] = "MAYBE"
    with pytest.raises(ContractValidationError):
        validate_contract("provider-run-result.schema.json", malformed)


def test_empty_request_strings_are_rejected_by_model_and_schema() -> None:
    with pytest.raises(ValueError, match="period must not be blank"):
        ProviderRequest(ProviderOperation.CALENDAR, period=" ")

    document = _result().to_dict()
    malformed = deepcopy(document)
    malformed["capabilities"][0]["registration"]["request"]["period"] = " "
    with pytest.raises(ContractValidationError):
        validate_contract("provider-run-result.schema.json", malformed)


def test_unknown_v2_capability_has_no_public_legacy_bridge() -> None:
    assert not hasattr(providers, "legacy_capability")
    with pytest.raises(ValueError, match="explicit registration"):
        Capability("new-undeclared-v2-feature", CapabilityStatus.PASS)
    from market_monitor.providers.base import _legacy_adapter_capability

    with pytest.raises(ValueError, match="unrecognized legacy adapter capability"):
        _legacy_adapter_capability("new-undeclared-v2-feature", CapabilityStatus.PASS)


def test_time_ranges_are_timezone_aware_and_ordered_in_model_and_schema() -> None:
    with pytest.raises(ValueError, match="earliest"):
        CapabilityEvidence(
            "reverse evidence range",
            earliest="2026-08-05T09:00:00+08:00",
            latest="2026-08-05T00:30:00+00:00",
        )
    with pytest.raises(ValueError, match="started_at"):
        ProviderRunResult(
            "reverse-run",
            SourceDescription("fixture-provider", "Fixture Provider", "Fixed test source"),
            "2026-08-05T00:00:01+00:00",
            "2026-08-05T00:00:00+00:00",
            (),
        )
    with pytest.raises(ValueError, match="ISO 8601"):
        CapabilityEvidence("naive timestamp", earliest="2026-08-05T00:00:00")

    document = _result().to_dict()
    malformed = deepcopy(document)
    malformed["started_at"] = "2026-08-05T09:00:00+08:00"
    malformed["completed_at"] = "2026-08-05T00:30:00+00:00"
    with pytest.raises(ContractValidationError, match="started_at"):
        validate_contract("provider-run-result.schema.json", malformed)
