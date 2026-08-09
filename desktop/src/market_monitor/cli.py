"""Machine-readable command-line entry points for the data producer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from market_monitor import __version__
from market_monitor.collector import run_fetch_session
from market_monitor.configuration import ConfigurationError, load_local_configuration
from market_monitor.control_center import serve_control_center
from market_monitor.package_builder import build_android_package
from market_monitor.report_pipeline import (
    build_chain_index,
    process_report_batch,
    report_status_summary,
    verify_report_batch,
)
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
    serve = subcommands.add_parser("serve", help="serve the local HTML control center")
    serve.add_argument("--data-root", type=Path, default=Path("data"))
    serve.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="bind port (0 picks a free port)")
    serve.add_argument("--timeout-seconds", type=float, default=None, help="stop after N seconds (tests/CI)")
    serve.add_argument("--quiet", action="store_true", help="suppress per-request HTTP logs")
    fetch = subcommands.add_parser("fetch", help="run a real data-fetch session and persist results")
    fetch.add_argument("--data-root", type=Path, default=Path("data_control"))
    fetch.add_argument("--limit-futures", type=int, default=15, help="number of domestic futures main contracts to fetch")
    fetch.add_argument("--limit-cn-stocks", type=int, default=5, help="number of CN stocks to fetch as samples")
    fetch.add_argument("--max-workers", type=int, default=4, help="concurrent fetch workers")
    fetch.add_argument("--task-timeout-seconds", type=float, default=90.0, help="per-task wall-clock timeout")
    package = subcommands.add_parser("package", help="build and sign an immutable Android sync package")
    package.add_argument("--data-root", type=Path, default=Path("data_control"))
    package.add_argument(
        "--private-key",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "keys" / "market_package_private_key.pem",
        help="Ed25519 private key used to sign the package",
    )
    package.add_argument(
        "--ecdsa-private-key",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "keys" / "market_package_ecdsa_private.pem",
        help="ECDSA P-256 private key used for Android fallback signature",
    )
    package.add_argument("--minimum-app-version", default="0.1.0", help="minimum Android app version")
    reports = subcommands.add_parser("reports", help="industry research report knowledge-base pipeline")
    report_subcommands = reports.add_subparsers(dest="report_command", parser_class=_Parser)
    process = report_subcommands.add_parser("process", help="parse and extract facts from PDF reports")
    process.add_argument("--report-root", type=Path, default=Path("行业产业链研报"))
    process.add_argument("--output-root", type=Path, default=Path("reports/industry"))
    process.add_argument("--workers", type=int, default=4)
    process.add_argument("--limit", type=int, default=0, help="process only the first N reports (0=all)")
    process.add_argument("--version", type=int, default=1)
    status = report_subcommands.add_parser("status", help="show per-report pipeline status")
    status.add_argument("--output-root", type=Path, default=Path("reports/industry"))
    verify = report_subcommands.add_parser("verify", help="scripted review/verify of extracted reports")
    verify.add_argument("--output-root", type=Path, default=Path("reports/industry"))
    verify.add_argument("--workers", type=int, default=4)
    chains = report_subcommands.add_parser("chains", help="aggregate extracted facts into industry chains")
    chains.add_argument("--output-root", type=Path, default=Path("reports/industry"))
    chains.add_argument("--max-facts-per-chain", type=int, default=200)
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
        if args.command == "serve":
            return _serve(args)
        if args.command == "fetch":
            return _fetch(args)
        if args.command == "package":
            return _package(args)
        if args.command == "reports":
            return _reports(args)
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


def _serve(args: argparse.Namespace) -> int:
    if args.timeout_seconds is not None and args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    try:
        host, port = serve_control_center(
            args.data_root,
            host=args.host,
            port=args.port,
            timeout_seconds=args.timeout_seconds,
            quiet=args.quiet,
        )
    except KeyboardInterrupt:
        _emit("SUCCESS", EXIT_SUCCESS, message="control center stopped by user")
        return EXIT_SUCCESS
    _emit("SUCCESS", EXIT_SUCCESS, message=f"control center served at http://{host}:{port}/")
    return EXIT_SUCCESS


def _fetch(args: argparse.Namespace) -> int:
    if args.limit_futures <= 0:
        raise ValueError("--limit-futures must be positive")
    if args.limit_cn_stocks <= 0:
        raise ValueError("--limit-cn-stocks must be positive")
    summary = run_fetch_session(
        args.data_root,
        max_workers=args.max_workers,
        task_timeout_seconds=args.task_timeout_seconds,
        limit_futures=args.limit_futures,
        limit_cn_stocks=args.limit_cn_stocks,
    )
    exit_code = EXIT_SUCCESS if summary["status"] == "PASS" else EXIT_PARTIAL_FAILURE
    _emit(
        summary["status"],
        exit_code,
        message=(
            f"session {summary['session_id']}: {summary['passed']} passed, "
            f"{summary.get('partial_failure', 0)} partial, "
            f"{summary['failed']} failed, {summary['blocked']} blocked, "
            f"{summary['total_rows']} rows"
        ),
    )
    return exit_code


def _package(args: argparse.Namespace) -> int:
    summary = build_android_package(
        args.data_root,
        args.private_key,
        ecdsa_private_key=args.ecdsa_private_key,
        minimum_app_version=args.minimum_app_version,
    )
    _emit(
        "SUCCESS",
        EXIT_SUCCESS,
        message=(
            f"package {summary['package_id']}: {summary['bars']} bars, "
            f"{summary['gold_metrics']} gold metrics, {summary['package_bytes']} bytes"
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return EXIT_SUCCESS


def _reports(args: argparse.Namespace) -> int:
    if args.report_command == "process":
        if args.workers <= 0:
            raise ValueError("--workers must be positive")
        if args.limit < 0:
            raise ValueError("--limit must be non-negative")
        summary = process_report_batch(
            args.report_root,
            args.output_root,
            workers=args.workers,
            limit=args.limit,
            version=args.version,
        )
        _emit(
            "SUCCESS" if summary["failed"] == 0 else "PARTIAL_FAILURE",
            EXIT_SUCCESS if summary["failed"] == 0 else EXIT_PARTIAL_FAILURE,
            message=(
                f"reports: {summary['processed']} processed, {summary['skipped']} skipped, "
                f"{summary['failed']} failed, {summary['facts']} facts"
            ),
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return EXIT_SUCCESS
    if args.report_command == "status":
        summary = report_status_summary(args.output_root)
        _emit("SUCCESS", EXIT_SUCCESS, message=f"reports status: {summary['total']} tracked")
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return EXIT_SUCCESS
    if args.report_command == "verify":
        if args.workers <= 0:
            raise ValueError("--workers must be positive")
        summary = verify_report_batch(args.output_root, workers=args.workers)
        _emit(
            "SUCCESS" if summary["failed"] == 0 and summary["flagged"] == 0 else "PARTIAL_FAILURE",
            EXIT_SUCCESS if summary["failed"] == 0 and summary["flagged"] == 0 else EXIT_PARTIAL_FAILURE,
            message=(
                f"reports verify: {summary['passed']} passed, "
                f"{summary['flagged']} flagged, {summary['failed']} failed"
            ),
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return EXIT_SUCCESS
    if args.report_command == "chains":
        index = build_chain_index(args.output_root, max_facts_per_chain=args.max_facts_per_chain)
        _emit(
            "SUCCESS",
            EXIT_SUCCESS,
            message=f"industry chains: {index['chain_count']} chains, {index['report_count']} reports",
        )
        print(json.dumps(index, ensure_ascii=False, sort_keys=True))
        return EXIT_SUCCESS
    raise ValueError("missing reports subcommand (process|status|verify|chains)")


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
