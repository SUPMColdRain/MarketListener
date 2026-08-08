"""Machine-readable command-line entry points for the data producer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from market_monitor import __version__
from market_monitor.configuration import ConfigurationError, load_local_configuration
from market_monitor.providers.comparison import compare_daily_bars, write_comparison
from market_monitor.providers.registry import registered_providers
from market_monitor.providers.runner import ProbeRunner, redact_secrets


EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 2
EXIT_CONFIGURATION = 3
EXIT_ARGUMENT = 64


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="market-monitor",
        description="Market monitor desktop producer CLI skeleton.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", parser_class=_Parser)
    probe = subcommands.add_parser("probe", help="probe registered external providers")
    probe.add_argument("--report-dir", type=Path, default=Path("reports"))
    probe.add_argument("--config-file", type=Path, help="explicit local env file outside the repository")
    probe.add_argument("--provider", action="append", dest="providers", help="provider name; repeat to select")
    probe.add_argument("--timeout-seconds", type=float, default=45.0, help="maximum wall-clock time per provider invocation")
    compare = subcommands.add_parser("compare-sources", help="compare registered source data without blending rows")
    compare.add_argument("--report-dir", type=Path, default=Path("reports"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "probe":
            return _probe(args)
        if args.command == "compare-sources":
            providers = {provider.name: provider for provider in registered_providers()}
            report = compare_daily_bars(providers["joinquant"], providers["baostock"])
            machine_path, human_path = write_comparison(report, args.report_dir)
            _emit("SUCCESS", EXIT_SUCCESS, reports=[str(machine_path), str(human_path)])
            return EXIT_SUCCESS
        _emit("SUCCESS", EXIT_SUCCESS, message="market-monitor desktop skeleton ready")
        return EXIT_SUCCESS
    except (ValueError, ConfigurationError) as error:
        _emit("ARGUMENT_ERROR", EXIT_ARGUMENT, message=redact_secrets(str(error)))
        return EXIT_ARGUMENT


def _probe(args: argparse.Namespace) -> int:
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    repository_root = Path(__file__).resolve().parents[3]
    configuration = load_local_configuration(config_file=args.config_file, repo_root=repository_root)
    providers = registered_providers(configuration.values)
    if args.providers:
        available = {provider.name for provider in providers}
        if any(name not in available for name in args.providers):
            raise ValueError("an unknown provider was requested")
        providers = tuple(provider for provider in providers if provider.name in args.providers)
    report = ProbeRunner(timeout_seconds=args.timeout_seconds, secret_values=configuration.secret_values).run(providers)
    machine_path, human_path = ProbeRunner(secret_values=configuration.secret_values).write_reports(report, args.report_dir)
    statuses = [capability.status.value for result in report.results for capability in result.capabilities]
    if statuses and all(status == "BLOCKED" for status in statuses):
        exit_code, status = EXIT_CONFIGURATION, "CONFIGURATION_BLOCKED"
    elif any(status in {"FAILED", "BLOCKED"} for status in statuses):
        exit_code, status = EXIT_PARTIAL_FAILURE, "PARTIAL_FAILURE"
    else:
        exit_code, status = EXIT_SUCCESS, "SUCCESS"
    _emit(status, exit_code, reports=[str(machine_path), str(human_path)], secret_values=configuration.secret_values)
    return exit_code


def _emit(
    status: str,
    exit_code: int,
    *,
    message: str | None = None,
    reports: list[str] | None = None,
    secret_values: tuple[str, ...] = (),
) -> None:
    payload: dict[str, object] = {"status": status, "exit_code": exit_code}
    if message:
        payload["message"] = message
    if reports:
        payload["reports"] = reports
    print(json.dumps(redact_secrets(payload, secret_values=secret_values), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
