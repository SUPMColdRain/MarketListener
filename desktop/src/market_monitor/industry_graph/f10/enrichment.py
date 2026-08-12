"""Multi-source F10 enrichment orchestrator.

This is the Phase 4 pipeline that turns the existing single-source
(Eastmoney) detail cache into a canonical, multi-source record:

1. Load the latest per-stock record from ``data_control/f10/{cn,hk}``.
2. Compute missing canonical fields with the planner.
3. Request only the provider pages that can fill those fields.
4. Merge provider observations non-destructively (existing values win,
   ``products`` is a union, every filled field keeps provenance).
5. Append the enriched record back to the same ``details_*.jsonl`` stream
   (old files/lines are never deleted, so this is a forward-only migration).
6. Optionally merge structured revenue rows into ``revenue_*.jsonl``.
7. Re-export ``industry/f10/*.jsonl`` so the F10 repository/API sees the
   enriched fields.

The pipeline never invents facts: absent values stay absent and are simply
not filled by any provider.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from market_monitor import f10 as f10_service

from .market_caps import derive_market_caps
from .planner import (
    compute_missing_fields,
    merge_profile_results,
    plan_revenue_requests,
    plan_requests,
)
from .providers import (
    F10Governance,
    F10Provider,
    ProviderBlocked,
    ProviderError,
    ProviderResult,
    get_governance,
    list_providers,
)
from .segments import migrate_revenue_rows

ENRICHMENT_VERSION = 1
_MARKER_KEY = "_enrichment"
_PERSIST_LOCK = threading.Lock()

# HKEX security-code aliases: some historical HKEX exports carry the
# superseded code next to the current one for the same issuer (e.g. 02997 is
# the old 1000-share lot code for 津上精密机床(中国)有限公司, whose current
# HKEX code is 01651 with a 500-share lot).  A superseded code must never
# trigger provider requests or count as a data failure: it is skipped and
# recorded as superseded so the canonical code remains the only enriched one.
SUPERSEDED_CODES: dict[str, dict[str, dict[str, str]]] = {
    "HK": {
        "02997": {
            "canonical": "01651",
            "reason": "HKEX current code is 01651 (500-share lot); 02997 is the superseded 1000-share lot code for the same issuer",
        },
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pid_alive(pid: int) -> bool:
    """Return True when ``pid`` refers to a live process on this host."""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _acquire_global_enrichment_lock(root: Path) -> bool:
    """Try to acquire the single-instance enrichment lock (all markets).

    CN/HK must not run two enrichment processes side by side: the central
    rate limiter is per-process, so two processes would bypass the configured
    global request budget.  A stale lock (dead PID) is recycled automatically.
    """
    lock_dir = Path(root) / "f10"
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    lock_file = lock_dir / "enrichment.lock"
    if lock_file.is_file():
        try:
            old_pid = int(lock_file.read_text(encoding="utf-8").strip())
            if _pid_alive(old_pid):
                return False
        except Exception:
            pass
    try:
        lock_file.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError:
        return False


def _release_global_enrichment_lock(root: Path) -> None:
    """Remove the global enrichment lock when we still own it."""
    lock_file = Path(root) / "f10" / "enrichment.lock"
    try:
        if lock_file.is_file():
            try:
                current = int(lock_file.read_text(encoding="utf-8").strip())
            except Exception:
                current = None
            if current is None or current == os.getpid():
                lock_file.unlink()
    except OSError:
        pass


def _record_key(code: str) -> str:
    return str(code or "").strip().upper()


def already_enriched(record: Mapping[str, Any], *, version: int = ENRICHMENT_VERSION) -> bool:
    """Return True when a record already carries our enrichment marker."""
    marker = record.get(_MARKER_KEY) or record.get("enrichment")
    return isinstance(marker, Mapping) and int(marker.get("version") or 0) >= version


def load_revenue_rows(root: Path, market: str, code: str) -> list[dict[str, Any]]:
    """Return the latest structured revenue rows observed for one code."""
    directory = Path(root) / "f10" / market.lower()
    latest: list[dict[str, Any]] = []
    if not directory.is_dir():
        return latest
    key = _record_key(code)
    for path in sorted(directory.glob("revenue_*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _record_key(payload.get("code")) == key:
                    rows = payload.get("revenue_breakdown") or []
                    if isinstance(rows, list):
                        latest = [row for row in rows if isinstance(row, Mapping)]
        except OSError:
            continue
    return latest


def _load_quote(root: Path, market: str, code: str) -> dict[str, Any]:
    """Return the most recent quote row for one code (no network)."""
    directory = Path(root) / "f10" / market.lower()
    latest: dict[str, Any] = {}
    if not directory.is_dir():
        return latest
    key = _record_key(code)
    for path in sorted(directory.glob("quotes_*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for row in payload.get("rows") or []:
                    if isinstance(row, Mapping) and _record_key(row.get("code")) == key:
                        latest = dict(row)
        except OSError:
            continue
    return latest


def _build_quote_index(root: Path, market: str) -> dict[str, dict[str, Any]]:
    """Return a code -> latest quote row index for the whole market.

    Equivalent to calling :func:`_load_quote` for every code, but reads each
    quotes file once instead of once per company.
    """

    directory = Path(root) / "f10" / market.lower()
    index: dict[str, dict[str, Any]] = {}
    if not directory.is_dir():
        return index
    for path in sorted(directory.glob("quotes_*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for row in payload.get("rows") or []:
                    if not isinstance(row, Mapping):
                        continue
                    key = _record_key(row.get("code"))
                    if key:
                        index[key] = dict(row)
        except OSError:
            continue
    return index


def _build_revenue_index(root: Path, market: str) -> dict[str, list[dict[str, Any]]]:
    """Return a code -> latest revenue rows index for the whole market.

    Equivalent to calling :func:`load_revenue_rows` for every code, but reads
    each revenue file once instead of once per company.
    """

    directory = Path(root) / "f10" / market.lower()
    index: dict[str, list[dict[str, Any]]] = {}
    if not directory.is_dir():
        return index
    for path in sorted(directory.glob("revenue_*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = _record_key(payload.get("code"))
                if not key:
                    continue
                rows = payload.get("revenue_breakdown") or []
                if isinstance(rows, list):
                    index[key] = [row for row in rows if isinstance(row, Mapping)]
        except OSError:
            continue
    return index


def merge_revenue_rows(
    base_rows: Sequence[Mapping[str, Any]],
    results: Sequence[Any],
) -> tuple[list[dict[str, Any]], int]:
    """Merge provider revenue rows non-destructively.

    Existing rows win and keep their order; rows already present (same name,
    report period, classification and source) are not duplicated.  Returns
    the merged list plus the number of newly added rows.
    """

    merged: list[dict[str, Any]] = [dict(row) for row in base_rows]
    seen: set[tuple[str, str, str, str]] = set()
    for row in merged:
        seen.add(_revenue_key(row))
    added = 0
    for result in results:
        rows = getattr(result, "revenue_breakdown", None) or ()
        if not rows and isinstance(result, Mapping):
            rows = result.get("revenueBreakdown") or result.get("revenue_breakdown") or ()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            key = _revenue_key(row)
            if key in seen:
                continue
            clean = dict(row)
            clean.setdefault("source", getattr(result, "provider", None) or "unknown")
            if not clean.get("fetched_at"):
                clean["fetched_at"] = getattr(result, "fetched_at", None) or _now()
            merged.append(clean)
            seen.add(key)
            added += 1
    return merged, added


def _revenue_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    name = str(row.get("item_name") or row.get("item") or row.get("name") or "").strip().casefold()
    period = str(row.get("period") or "").strip()[:10]
    classification = str(row.get("classification") or row.get("type") or "").strip().casefold()
    source = str(row.get("source") or "").strip().casefold()
    return (name, period, classification, source)


def enrich_one(
    root: Path,
    *,
    market: str,
    code: str,
    records: Mapping[str, Mapping[str, Any]] | None = None,
    providers: Mapping[str, F10Provider] | None = None,
    governance: F10Governance | None = None,
    force: bool = False,
    quote_index: Mapping[str, Mapping[str, Any]] | None = None,
    revenue_index: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    quote_cache: Mapping[str, tuple[dict[str, Any], str]] | None = None,
) -> dict[str, Any]:
    """Enrich one company's latest detail record and persist it."""
    market_key = market.upper()
    if market_key not in {"CN", "HK"}:
        raise ValueError("market must be CN or HK")
    root = Path(root)
    if records is None:
        records = f10_service._load_existing_records(root, market_key)
    providers = dict(providers or list_providers())
    governance = governance or get_governance()
    code_key = _record_key(code)
    base = dict(records.get(code_key) or records.get(code) or {})
    base.setdefault("code", code)
    base.setdefault("market", market_key)
    superseded = (SUPERSEDED_CODES.get(market_key) or {}).get(code_key)
    if superseded:
        canonical = superseded.get("canonical") or ""
        return {
            "code": code,
            "market": market_key,
            "status": "SKIPPED",
            "reason": f"superseded_by_{canonical}",
            "canonicalCode": canonical,
        }
    if not force and already_enriched(base):
        return {
            "code": code,
            "market": market_key,
            "status": "SKIPPED",
            "reason": "already_enriched",
        }

    missing = compute_missing_fields(base)
    requests, remaining = plan_requests(missing, providers, market=market_key)
    results: list[ProviderResult] = []
    errors: list[dict[str, str]] = []
    for provider_name, page in requests:
        provider = providers.get(provider_name)
        if provider is None:
            errors.append({"provider": provider_name, "error": "provider not available"})
            continue
        if provider_name == "tencent" and quote_cache and page == "bulk_quote":
            cached = quote_cache.get(code_key) or quote_cache.get(code)
            if cached:
                fields, cached_at = cached
                results.append(
                    ProviderResult(
                        provider="tencent",
                        page="bulk_quote",
                        market=market_key,
                        code=code,
                        fetched_at=cached_at,
                        fields=dict(fields),
                        provenance={
                            key: {
                                "source": "tencent",
                                "sourcePage": "bulk_quote",
                                "fetchedAt": cached_at,
                            }
                            for key in fields
                            if key != "code"
                        },
                    )
                )
                continue
        try:
            results.append(provider.fetch_profile(code, market=market_key, pages=(page,)))
        except (ProviderBlocked, ProviderError) as error:
            errors.append({"provider": provider_name, "page": page, "error": str(error)[:240]})
        except Exception as error:  # noqa: BLE001 - keep one bad source from killing a run
            errors.append(
                {
                    "provider": provider_name,
                    "page": page,
                    "error": f"{type(error).__name__}: {error}"[:240],
                }
            )

    merged = merge_profile_results(base, results) if results else dict(base)
    if quote_index is None:
        quote = _load_quote(root, market_key, code)
    else:
        quote = dict(quote_index.get(code_key) or {})
    if quote:
        embedded = dict(merged.get("quote") or {})
        for key, value in quote.items():
            if value not in (None, "") and embedded.get(key) in (None, ""):
                embedded[key] = value
        merged["quote"] = embedded
        merged.setdefault("quote_time", quote.get("quote_time") or embedded.get("quote_time"))
        merged.setdefault("quote_source", quote.get("quote_source") or "tencent_quote")
    total_cap, float_cap, cap_reasons = derive_market_caps(merged, merged.get("quote"), market=market_key)
    if total_cap is not None:
        merged["total_market_cap"] = total_cap
    if float_cap is not None:
        merged["float_market_cap"] = float_cap
    revenue_results: list[ProviderResult] = []
    revenue_requests: list[tuple[str, str]] = []
    if revenue_index is None:
        existing_revenue = load_revenue_rows(root, market_key, code)
    else:
        existing_revenue = [dict(row) for row in (revenue_index.get(code_key) or [])]
    if not existing_revenue:
        revenue_requests = plan_revenue_requests(providers, market=market_key)
    for provider_name, _page in revenue_requests:
        provider = providers.get(provider_name)
        if provider is None:
            continue
        try:
            revenue_results.append(provider.fetch_revenue(code, market=market_key))
        except (ProviderBlocked, ProviderError) as error:
            errors.append({"provider": provider_name, "revenue": True, "error": str(error)[:240]})
        except Exception as error:  # noqa: BLE001
            errors.append(
                {
                    "provider": provider_name,
                    "revenue": True,
                    "error": f"{type(error).__name__}: {error}"[:240],
                }
            )

    revenue_rows, revenue_added = merge_revenue_rows(existing_revenue, revenue_results)
    revenue_rows, revenue_migrated = migrate_revenue_rows(revenue_rows)
    filled = sorted(field for field in missing if field in merged and merged.get(field))
    if (
        missing
        and not results
        and not revenue_results
        and (requests or revenue_requests)
    ):
        return {
            "code": code,
            "market": market_key,
            "status": "FAILED",
            "reason": "no_provider_success",
            "missingBefore": sorted(missing),
            "errors": errors,
        }
    fetched_at = _now()
    marker = {
        "version": ENRICHMENT_VERSION,
        "enrichedAt": fetched_at,
        "providers": sorted({result.provider for result in results} | {result.provider for result in revenue_results}),
        "requests": [{"provider": name, "page": page} for name, page in requests],
        "filledFields": filled,
        "remainingFields": sorted(remaining),
        "errors": errors,
        "marketCapMissing": cap_reasons or {},
    }
    merged[_MARKER_KEY] = marker
    merged.setdefault("created_at", merged.get("detail_fetched_at") or fetched_at)
    merged["enriched_at"] = fetched_at
    merged["source"] = merged.get("source") or "eastmoney_f10 + multi_source"
    with _PERSIST_LOCK:
        f10_service._append_jsonl(f10_service._record_path(root, market_key, "details"), merged)
    if records is not None:
        records[code_key] = merged
    if revenue_rows and (revenue_added or revenue_migrated):
        with _PERSIST_LOCK:
            f10_service._append_jsonl(
                f10_service._record_path(root, market_key, "revenue"),
                {
                    "code": code,
                    "revenue_breakdown": revenue_rows,
                    "fetched_at": fetched_at,
                    "enriched": True,
                    "enrichment_version": ENRICHMENT_VERSION,
                },
            )
    return {
        "code": code,
        "market": market_key,
        "status": "PASS",
        "missingBefore": sorted(missing),
        "filledFields": filled,
        "remainingFields": sorted(remaining),
        "requests": [f"{name}/{page}" for name, page in requests],
        "revenueAdded": revenue_added,
        "revenueMigrated": revenue_migrated,
        "marketCapMissing": cap_reasons or {},
        "errors": errors,
    }


def enrich_batch(
    root: Path,
    *,
    market: str = "CN",
    codes: Sequence[str] | None = None,
    limit: int | None = None,
    providers: Mapping[str, F10Provider] | None = None,
    governance: F10Governance | None = None,
    force: bool = False,
    checkpoint_every: int = 25,
    workers: int = 1,
) -> dict[str, Any]:
    """Enrich every company (or a subset) and checkpoint between codes."""
    market_key = market.upper()
    if market_key not in {"CN", "HK"}:
        raise ValueError("market must be CN or HK")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be at least 1")
    if workers < 1:
        raise ValueError("workers must be at least 1")
    root = Path(root)
    if not _acquire_global_enrichment_lock(root):
        state_path = root / "f10" / market_key.lower() / "enrichment_state.json"
        return {
            "market": market_key,
            "startedAt": _now(),
            "completedAt": _now(),
            "requested": 0,
            "passed": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [
                {
                    "code": "__lock__",
                    "error": "another enrichment process holds the global run lock",
                }
            ],
            "checkpoint": str(state_path),
            "status": "SKIPPED",
            "message": f"f10 {market_key} enrichment skipped (global lock held)",
        }
    atexit.register(_release_global_enrichment_lock, root)
    started_at = _now()
    provider_map = dict(providers or list_providers())
    records: dict[str, dict[str, Any]] = dict(f10_service._load_existing_records(root, market_key))
    if codes is None:
        codes = [str(record.get("code") or "") for record in records.values() if record.get("code")]
    codes = [code for code in codes if str(code or "").strip()]
    selected = codes[:limit] if limit is not None else codes
    done: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    failed_details: list[dict[str, Any]] = []
    prefetch_errors: list[dict[str, str]] = []
    state_path = root / "f10" / market_key.lower() / "enrichment_state.json"
    quote_index = _build_quote_index(root, market_key)
    revenue_index = _build_revenue_index(root, market_key)
    quote_cache: dict[str, tuple[dict[str, Any], str]] = {}
    tencent_provider = provider_map.get("tencent")
    if tencent_provider is not None:
        needed: list[str] = []
        for code in selected:
            code_key = _record_key(code)
            base = records.get(code_key) or records.get(code) or {}
            if not force and already_enriched(base):
                continue
            missing = compute_missing_fields(base)
            requests, _remaining = plan_requests(missing, provider_map, market=market_key)
            if any(name == "tencent" and page == "bulk_quote" for name, page in requests):
                needed.append(str(code))
        if needed:
            try:
                fetched_map = tencent_provider.fetch_quotes(needed, market=market_key)
                cached_at = _now()
                quote_cache = {
                    _record_key(code): (dict(fields), cached_at)
                    for code, fields in fetched_map.items()
                    if fields
                }
            except Exception as error:  # noqa: BLE001 - fall back to per-company fetch
                prefetch_errors.append(
                    {
                        "code": "__tencent_prefetch__",
                        "error": f"{type(error).__name__}: {error}"[:240],
                    }
                )
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="f10-enrich") as pool:
        future_to_code = {
            pool.submit(
                enrich_one,
                root,
                market=market_key,
                code=code,
                records=records,
                providers=provider_map,
                governance=governance,
                force=force,
                quote_index=quote_index,
                revenue_index=revenue_index,
                quote_cache=quote_cache,
            ): code
            for code in selected
        }
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                result = future.result()
                done.append(result)
                if result.get("status") == "FAILED":
                    failed_details.append(
                        {
                            "code": code,
                            "reason": str(result.get("reason") or "failed")[:240],
                            "providerErrors": result.get("errors") or [],
                        }
                    )
            except Exception as error:  # noqa: BLE001 - batch must keep going
                errors.append({"code": code, "error": f"{type(error).__name__}: {error}"[:240]})
                done.append({"code": code, "market": market_key, "status": "FAILED"})
            if len(done) % checkpoint_every == 0 or len(done) == len(selected):
                _save_checkpoint(
                    state_path,
                    {
                        "updated_at": _now(),
                        "market": market_key,
                        "total": len(selected),
                        "processed": len(done),
                        "passed": sum(1 for item in done if item.get("status") == "PASS"),
                        "skipped": sum(1 for item in done if item.get("status") == "SKIPPED"),
                        "failed": sum(1 for item in done if item.get("status") == "FAILED"),
                        "codes": [str(item.get("code") or "") for item in done],
                        "supersededCodes": {
                            code_key: entry["canonical"]
                            for code_key, entry in (SUPERSEDED_CODES.get(market_key) or {}).items()
                        },
                    },
                )

    export_errors: list[dict[str, str]] = []
    try:
        f10_service.export_atlas_f10(root, markets=(market_key,))
    except Exception as error:  # never fail enrichment because export failed
        export_errors.append({"code": "__atlas_export__", "error": f"{type(error).__name__}: {error}"[:300]})
    try:
        _refresh_catalog(root, market_key, records)
    except Exception as error:  # noqa: BLE001 - catalog refresh is best effort
        export_errors.append({"code": "__catalog_refresh__", "error": f"{type(error).__name__}: {error}"[:300]})
    all_errors = errors + failed_details + prefetch_errors + export_errors
    failed_summaries = sum(1 for item in done if item.get("status") == "FAILED")
    if not done and not all_errors:
        batch_status = "PASS"
    elif failed_summaries and failed_summaries == len(done):
        batch_status = "FAILED"
    elif all_errors or failed_summaries:
        batch_status = "PARTIAL_FAILURE"
    else:
        batch_status = "PASS"
    _release_global_enrichment_lock(root)
    summary = {
        "market": market_key,
        "startedAt": started_at,
        "completedAt": _now(),
        "requested": len(selected),
        "passed": sum(1 for item in done if item.get("status") == "PASS"),
        "skipped": sum(1 for item in done if item.get("status") == "SKIPPED"),
        "failed": failed_summaries,
        "errors": all_errors[-10:],
        "checkpoint": str(state_path),
        "supersededCodes": {
            code_key: entry["canonical"]
            for code_key, entry in (SUPERSEDED_CODES.get(market_key) or {}).items()
        },
        "governance": governance.stats() if governance is not None else None,
        "status": batch_status,
    }
    _append_run_summary(root, market_key, summary)
    return summary


def _append_run_summary(root: Path, market: str, summary: Mapping[str, Any]) -> None:
    """Append one authoritative JSON line per enrichment run.

    The line is the same dict returned to the CLI, so reports can always read
    the latest completed run even when stdout is redirected to a separate log.
    """
    market_key = market.upper()
    path = Path(root) / "f10" / market_key.lower() / "enrichment_runs.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(summary), ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _save_checkpoint(path: Path, state: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _refresh_catalog(root: Path, market: str, records: Mapping[str, Mapping[str, Any]]) -> None:
    """Upsert enriched detail rows into the existing DuckDB catalog table."""
    from market_monitor.storage import MarketStore

    market_key = market.upper()
    store = MarketStore(root)
    try:
        store.register_default_datasets()
        store.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS f10_company (
                code VARCHAR PRIMARY KEY,
                market VARCHAR,
                name VARCHAR,
                org_name VARCHAR,
                industry_em VARCHAR,
                industry_csrc VARCHAR,
                total_market_cap_yi DOUBLE,
                float_market_cap_yi DOUBLE,
                profile VARCHAR,
                business_scope VARCHAR,
                record JSON,
                fetched_at VARCHAR
            )
            """
        )
        for record in records.values():
            if str(record.get("market") or "").upper() != market_key:
                continue
            if not already_enriched(record):
                continue
            quote = record.get("quote") or {}
            total_cap = record.get("total_market_cap") or {}
            float_cap = record.get("float_market_cap") or {}
            total_yi = (
                float(total_cap["value"]) / 1e8
                if isinstance(total_cap, Mapping) and float(total_cap.get("value") or 0) > 0
                else quote.get("total_market_cap_yi")
            )
            float_yi = (
                float(float_cap["value"]) / 1e8
                if isinstance(float_cap, Mapping) and float(float_cap.get("value") or 0) > 0
                else quote.get("float_market_cap_yi")
            )
            store.connection.execute(
                """
                INSERT INTO f10_company
                (code, market, name, org_name, industry_em, industry_csrc,
                 total_market_cap_yi, float_market_cap_yi, profile, business_scope,
                 record, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    market = excluded.market,
                    name = excluded.name,
                    org_name = excluded.org_name,
                    industry_em = excluded.industry_em,
                    industry_csrc = excluded.industry_csrc,
                    total_market_cap_yi = excluded.total_market_cap_yi,
                    float_market_cap_yi = excluded.float_market_cap_yi,
                    profile = excluded.profile,
                    business_scope = excluded.business_scope,
                    record = excluded.record,
                    fetched_at = excluded.fetched_at
                """,
                [
                    record.get("code"),
                    market_key,
                    record.get("name"),
                    record.get("org_name"),
                    record.get("industry_em"),
                    record.get("industry_csrc"),
                    total_yi,
                    float_yi,
                    record.get("org_profile") or record.get("profile"),
                    record.get("business_scope"),
                    json.dumps(record, ensure_ascii=False),
                    record.get("enriched_at") or record.get("detail_fetched_at") or _now(),
                ],
            )
        store.connection.commit()
    finally:
        store.close()


__all__ = (
    "ENRICHMENT_VERSION",
    "already_enriched",
    "enrich_batch",
    "enrich_one",
    "load_revenue_rows",
    "merge_revenue_rows",
)
