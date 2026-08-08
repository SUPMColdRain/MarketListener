"""Stable, safe CLI outcomes without performing real provider probes."""

import json

from market_monitor.providers import (
    Capability,
    CapabilityRegistration,
    CapabilityStatus,
    ConfigurationRequirement,
    ErrorCategory,
    Provider,
    ProviderError,
    ProviderOperation,
    ProviderRequest,
)

from market_monitor import __version__
from market_monitor.cli import main
from market_monitor.configuration import LocalConfiguration


class _Provider(Provider):
    name = "test-provider"

    def __init__(self, capabilities=(), missing=()):
        self._capabilities = capabilities
        self._missing = missing

    def probe_capabilities(self):
        return self._capabilities

    def missing_configuration_requirements(self):
        return self._missing

    def fetch_instruments(self):
        raise NotImplementedError

    def fetch_bars(self):
        raise NotImplementedError

    def fetch_indicators(self):
        raise NotImplementedError

    def fetch_calendar(self):
        raise NotImplementedError

    def health_check(self):
        raise NotImplementedError


def _capability(status: CapabilityStatus) -> Capability:
    return Capability(
        "bars",
        status,
        detail="safe test result",
        registration=CapabilityRegistration("bars", "test bars", ProviderRequest(ProviderOperation.OTHER)),
        error=ProviderError(ErrorCategory.NETWORK, "safe failure") if status is CapabilityStatus.FAILED else None,
    )


def test_package_version_is_pinned() -> None:
    assert __version__ == "0.1.0"


def test_main_returns_success(capsys) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["status"] == "SUCCESS"


def test_probe_exit_codes_are_machine_readable_without_real_network(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("market_monitor.cli.registered_providers", lambda values=None: (_Provider([_capability(CapabilityStatus.FAILED)]),))

    assert main(["probe", "--report-dir", str(tmp_path)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["exit_code"] == 2
    assert payload["status"] == "PARTIAL_FAILURE"
    assert payload["reports"][0].endswith("provider-capabilities.json")
    assert payload["reports"][1].endswith("provider-capabilities.md")


def test_probe_configuration_and_argument_exit_codes(monkeypatch, tmp_path, capsys) -> None:
    missing = (ConfigurationRequirement("JQDATA_PASSWORD", "configuration-jqdata-password", "password required"),)
    monkeypatch.setattr("market_monitor.cli.registered_providers", lambda values=None: (_Provider(missing=missing),))

    assert main(["probe", "--report-dir", str(tmp_path)]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "CONFIGURATION_BLOCKED"
    assert main(["probe", "--timeout-seconds", "0"]) == 64
    assert json.loads(capsys.readouterr().out)["exit_code"] == 64


def test_cli_redacts_sensitive_report_directory_from_machine_output(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("market_monitor.cli.registered_providers", lambda values=None: (_Provider([_capability(CapabilityStatus.PASS)]),))
    report_dir = tmp_path / "apiKey=CLI_LEAK"

    assert main(["probe", "--report-dir", str(report_dir)]) == 0
    output = capsys.readouterr().out

    assert "CLI_LEAK" not in output
    assert "[redacted sensitive text]" in output
    assert (report_dir / "provider-capabilities.json").is_file()
    assert (report_dir / "provider-capabilities.md").is_file()


def test_cli_redacts_registered_short_secret_when_it_appears_as_a_report_path_token(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("market_monitor.cli.registered_providers", lambda values=None: (_Provider([_capability(CapabilityStatus.PASS)]),))
    monkeypatch.setattr("market_monitor.cli.load_local_configuration", lambda **_: LocalConfiguration({"JQDATA_PASSWORD": "s3"}))
    report_dir = tmp_path / "s3"

    assert main(["probe", "--report-dir", str(report_dir)]) == 0
    output = capsys.readouterr().out

    assert "s3" not in output
    assert "***" in output
