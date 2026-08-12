"""Simple batch F10 fetcher with file lock. Runs in a single process
and can be invoked directly from the command line as a long-running
background process. The file lock prevents duplicate processes from
fetching the same market simultaneously.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
from .f10 import _acquire_market_lock, _release_market_lock


def run(market: str, limit: int, delay: float, data_root: str = "../data_control"):
    root = Path(data_root)
    if not _acquire_market_lock(root, market):
        print(f"{market}: lock held by another process, exiting", flush=True)
        return 0, 0
    try:
        from .f10 import (
            load_a_share_universe, load_hk_universe,
            _load_existing_records, _load_state, _save_state,
            fetch_company_survey, _append_jsonl, _record_path, _now,
        )
        if market == "CN":
            uni = load_a_share_universe()
        else:
            uni = load_hk_universe(cache_dir=root / "f10" / "hk")
        codes = [item["code"] for item in uni]
        existing = _load_existing_records(root, market)
        state = _load_state(root, market)
        done_codes = set(str(c) for c in state.get("done", []))
        pending = [c for c in codes if c not in existing and c not in done_codes]
        print(f"{market}: universe={len(codes)} done={len(done_codes)} pending={len(pending)} limit={limit} delay={delay}", flush=True)
        fetched = 0
        errors = 0
        for i, code in enumerate(pending[:limit]):
            try:
                record = fetch_company_survey(code, market=market)
                record["market"] = market
                fetched_at = _now()
                record["created_at"] = fetched_at
                record["detail_fetched_at"] = fetched_at
                _append_jsonl(_record_path(root, market, "details"), record)
                fetched += 1
                done_codes.add(code)
                if (i + 1) % 25 == 0:
                    _save_state(root, market, {"done": sorted(done_codes), "failed": [], "updated_at": _now()})
                    print(f"  [{market}] {i+1}/{min(len(pending), limit)} fetched, last={code} OK", flush=True)
            except Exception as e:
                errors += 1
                msg = str(e)[:200]
                print(f"  [{market}] {i+1}/{min(len(pending), limit)} FAIL code={code}: {msg}", flush=True)
                if errors >= 8:
                    print(f"  [{market}] too many errors ({errors}), stopping", flush=True)
                    break
            if i + 1 < min(len(pending), limit):
                time.sleep(delay)
        _save_state(root, market, {"done": sorted(done_codes), "failed": [], "updated_at": _now()})
        print(f"{market}: fetched={fetched} errors={errors} total_done={len(done_codes)}", flush=True)
        return fetched, errors
    finally:
        _release_market_lock(root, market)


if __name__ == "__main__":
    market = sys.argv[1] if len(sys.argv) > 1 else "CN"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    data_root = sys.argv[4] if len(sys.argv) > 4 else "../data_control"
    run(market, limit, delay, data_root)
