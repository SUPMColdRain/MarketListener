"""Desktop producer CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from market_monitor import __version__
from market_monitor.providers.comparison import compare_daily_bars, write_comparison
from market_monitor.providers.registry import registered_providers
from market_monitor.providers.runner import ProbeRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-monitor",
        description="Market monitor desktop producer CLI skeleton.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subcommands = parser.add_subparsers(dest="command")
    probe = subcommands.add_parser("probe", help="probe registered external providers")
    probe.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports"),
        help="directory for machine-readable JSON and human-readable Markdown reports",
    )
    probe.add_argument(
        "--provider",
        action="append",
        dest="providers",
        help="provider name to run; repeat to select more than one",
    )
    probe.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
        help="maximum wall-clock time for each provider probe",
    )
    compare = subcommands.add_parser("compare-sources", help="compare registered source data without blending rows")
    compare.add_argument("--report-dir", type=Path, default=Path("reports"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "probe":
        runner = ProbeRunner(timeout_seconds=args.timeout_seconds)
        providers = registered_providers()
        if args.providers:
            providers = tuple(provider for provider in providers if provider.name in args.providers)
        report = runner.run(providers)
        machine_path, human_path = runner.write_reports(report, args.report_dir)
        print(f"provider reports written: {machine_path}, {human_path}")
        return 0
    if args.command == "compare-sources":
        providers = {provider.name: provider for provider in registered_providers()}
        report = compare_daily_bars(providers["joinquant"], providers["baostock"])
        machine_path, human_path = write_comparison(report, args.report_dir)
        print(f"comparison reports written: {machine_path}, {human_path}")
        return 0
    print("market-monitor desktop skeleton ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
