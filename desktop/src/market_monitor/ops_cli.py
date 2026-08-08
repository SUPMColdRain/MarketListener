"""CLI entry point for the nightly operational pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ops import JobStateStore, NightlyJob


_ALLOWED_STEPS = frozenset({"health_check", "package_from_silver"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-monitor-ops")
    subparsers = parser.add_subparsers(dest="command", required=True)
    nightly = subparsers.add_parser("nightly", help="run the nightly job pipeline")
    nightly.add_argument("--state", required=True, type=Path, help="job state sqlite path")
    nightly.add_argument("--steps", required=True, type=Path, help="JSON file with a fixed-step whitelist")
    nightly.add_argument("--data-root", type=Path, default=None, help="data root for health_check")
    nightly.add_argument("--output-dir", type=Path, default=None, help="package output directory")
    nightly.add_argument("--package-id", default=None, help="package id for package_from_silver")
    nightly.add_argument("--partition-id", default=None, help="silver partition id for package_from_silver")
    nightly.add_argument("--private-key", type=Path, default=None, help="signing private key")
    nightly.add_argument("--public-key", type=Path, default=None, help="signing public key")
    nightly.add_argument("--ledger", type=Path, default=None, help="package ledger sqlite path")
    nightly.add_argument("--resume", action="store_true", help="resume the last run of the same job id")
    nightly.add_argument("--job-id", default=None, help="explicit job id (default: generated)")
    args = parser.parse_args(argv)

    if args.command == "nightly":
        return _run_nightly(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def _run_nightly(args: argparse.Namespace) -> int:
    try:
        document = json.loads(args.steps.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        print(f"steps config error: {error}", file=sys.stderr)
        return 2
    names = document.get("steps")
    if not isinstance(names, list) or not names or any(name not in _ALLOWED_STEPS for name in names):
        print(f"steps must be a non-empty whitelist subset of {sorted(_ALLOWED_STEPS)}", file=sys.stderr)
        return 2
    if "health_check" in names and args.data_root is None:
        print("--data-root is required for health_check", file=sys.stderr)
        return 2
    if "package_from_silver" in names and (
        args.data_root is None
        or args.output_dir is None
        or not args.package_id
        or not args.partition_id
        or args.private_key is None
        or args.public_key is None
    ):
        print(
            "--data-root/--output-dir/--package-id/--partition-id/--private-key/--public-key are required for package_from_silver",
            file=sys.stderr,
        )
        return 2

    steps = [("health_check", _health_check(args.data_root))] if "health_check" in names else []
    if "package_from_silver" in names:
        steps.append(("package_from_silver", _package_from_silver(args)))
    store = JobStateStore(args.state)
    job = NightlyJob(store, steps, notify=lambda level, message: print(f"[{level}] {message}"))
    try:
        status = job.run(job_id=args.job_id, resume=args.resume)
    except Exception as error:  # noqa: BLE001 - CLI boundary
        print(f"job error: {error}", file=sys.stderr)
        return 1
    finally:
        store.close()
    return 0 if status == "PASS" else 1


def _health_check(data_root: Path) -> object:
    def check() -> None:
        if not data_root.exists():
            raise FileNotFoundError(f"data root missing: {data_root}")
        if not data_root.is_dir():
            raise NotADirectoryError(f"data root is not a directory: {data_root}")

    return check


def _package_from_silver(args: argparse.Namespace) -> object:
    def run() -> None:
        from .market_package import PackageLedger
        from .pipeline import MarketPipeline

        pipeline = MarketPipeline(
            data_root=args.data_root,
            state_path=args.state.with_suffix(".checkpoints.sqlite"),
            output_dir=args.output_dir,
            private_key_path=args.private_key,
            public_key_path=args.public_key,
        )
        try:
            bars, cutoff = pipeline.load_partition(args.partition_id)
            if not bars:
                raise ValueError(f"partition {args.partition_id} has no bars")
            data_cutoff = cutoff or "1970-01-01T00:00:00Z"
            report = pipeline.quality(args.package_id + "-partition", bars, data_cutoff)
            if report.blocking:
                raise ValueError("blocking quality issues; package skipped")
            ledger = PackageLedger(args.ledger) if args.ledger is not None else None
            try:
                pipeline.package(
                    package_id=args.package_id,
                    partition_id=report.partition_id,
                    bars=bars,
                    quality_report=report,
                    data_cutoff=data_cutoff,
                    source_run_summaries=[],
                    ledger=ledger,
                )
            finally:
                if ledger is not None:
                    ledger.close()
        finally:
            pipeline.close()

    return run


if __name__ == "__main__":
    raise SystemExit(main())
