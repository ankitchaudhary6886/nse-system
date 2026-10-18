"""One-click data refresh: the button behind the terminal UI.

WHY THIS EXISTS
---------------
The owner cannot spend daily time running commands. Everything is already
scheduled on the VM, but an on-demand refresh must be one press that (a) fetches
new bars from the free providers (and Fyers when a token/refresh token exists),
(b) recomputes the derived layers in dependency order, (c) writes an audit row,
and (d) reports progress so the UI can show what is happening. This module is
that orchestrator; it is deliberately framework-free so both the FastAPI button
and `python refresh_pipeline.py run` use the same code path.

GUARANTEES
- Only ONE refresh can run at a time (module lock); a second click returns
  immediately with already_running=True instead of corrupting the DB.
- Every step is independent and failure-isolated: one broken stage does not
  stop the rest, and the run is recorded as ok / partial / error.
- The chain runs in dependency order: prices -> technicals -> breadth -> ML ->
  scan -> PWin -> events -> institutional -> Top Picks -> patterns -> templates.
  (ML before scan matters: scan consumes same-day ML scores.)
- Writers still pass the freshness gate themselves; if the price spine is stale
  the derived stages refuse to write and say so in the run result.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import db

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {
    "run_id": None, "running": False, "status": "idle",
    "message": "No refresh has run yet.", "trigger": None,
    "started_at": None, "finished_at": None, "steps": [],
    "current": None, "index": 0, "total": 0,
}


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


# ---------------------------------------------------------------------------
# individual steps (lazy imports; each returns a JSON-able summary)
# ---------------------------------------------------------------------------
def _step_fyers() -> dict:
    import ingest_fyers
    import fyers_client
    client = fyers_client.FyersClient()
    if not client.token or client.token_store.expired():
        # Try the pin-based refresh flow before giving up; without FYERS_PIN
        # this raises and we fall through to the free providers.
        try:
            client.refresh_access_token()
        except Exception as exc:
            return {"skipped": f"no valid Fyers token: {exc}"}
    return ingest_fyers.sync_recent(days=15)


def _step_prices() -> dict:
    import ingest_prices
    import db as _db
    conn = _db.get_conn()
    try:
        failed = ingest_prices.run(show_every=0)
    finally:
        conn.close()
    return {"failed": len(failed or []), "failed_sample": (failed or [])[:10]}


def _step_official() -> dict:
    """FREE official NSE archives: raw prices + delivery + index closes.

    Runs before the per-symbol free providers: one archive file is faster and
    more authoritative than ~865 provider calls, and it carries delivery% and
    every index close as a bonus. Missing files are holidays, not failures.
    """
    import nse_eod_ingest
    import db as _db
    conn = _db.get_conn()
    try:
        return nse_eod_ingest.catch_up(conn, days_back=5)
    finally:
        conn.close()


def _step_fyers_gaps() -> dict:
    """Fill holes the official files could not cover, using Fyers (optional).

    Runs after official+free price ingest. With no token it returns a clean
    skip, so the chain behaves exactly as before.
    """
    import backfill_gaps
    import db as _db
    conn = _db.get_conn()
    try:
        return backfill_gaps.fill_with_fyers(conn, days=10)
    finally:
        conn.close()


def _step_technicals() -> dict:
    import technicals
    technicals.compute_all()
    return {"ok": True}


def _step_breadth() -> dict:
    import breadth
    return breadth.compute(force=True)


def _step_ml() -> dict:
    import ml_predict
    ml_predict.predict_all()
    return {"ok": True}


def _step_scan() -> dict:
    import scan
    scan.run()
    return {"ok": True}


def _step_pwin() -> dict:
    import pwin_cache
    return {"computed": pwin_cache.refresh_all()}


def _step_events() -> dict:
    import events
    return {"detected": events.detect()}


def _step_institutional() -> dict:
    import institutional
    return {"rows": institutional.refresh()}


def _step_toppicks() -> dict:
    import top_picks
    top_picks.compute(force=True)
    return {"ok": True}


def _step_patterns() -> dict:
    import patterns
    return patterns.run()


def _step_templates() -> dict:
    import template_match
    return {"saved": template_match.run()}


def default_steps(include_detectors: bool = True) -> List[Tuple[str, Callable[[], Any]]]:
    steps: List[Tuple[str, Callable[[], Any]]] = [
        ("fyers", _step_fyers),
        ("official_nse", _step_official),
        ("prices", _step_prices),
        ("fyers_gaps", _step_fyers_gaps),
        ("technicals", _step_technicals),
        ("breadth", _step_breadth),
        ("ml", _step_ml),
        ("scan", _step_scan),
        ("pwin", _step_pwin),
        ("events", _step_events),
        ("institutional", _step_institutional),
        ("top_picks", _step_toppicks),
    ]
    if include_detectors:
        steps += [("patterns", _step_patterns), ("templates", _step_templates)]
    return steps


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def _record(conn, run_id: str, started: str, status: str,
            steps: List[dict], error: Optional[str] = None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO refresh_runs "
        "(run_id, started_at, finished_at, status, trigger, steps_json, error) "
        "VALUES (?,?,?,?,?,?,?)",
        (run_id, started, now_ist().isoformat(timespec="seconds"), status,
         _STATE.get("trigger"), json.dumps(steps, default=str)[:200000], error))
    conn.commit()


def run(trigger: str = "manual", include_detectors: bool = True,
        steps: Optional[Sequence[Tuple[str, Callable[[], Any]]]] = None,
        conn=None, run_id: Optional[str] = None) -> dict:
    """Run the refresh chain. Never raises; returns a summary dict."""
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "already_running": True, "status": "running",
                "message": "A refresh is already running."}
    own_conn = conn is None
    run_id = run_id or uuid.uuid4().hex[:12]
    started = now_ist().isoformat(timespec="seconds")
    chain = list(steps if steps is not None else default_steps(include_detectors))
    _STATE.update({"run_id": run_id, "running": True, "status": "running",
                   "message": "Refresh started", "trigger": trigger,
                   "started_at": started, "finished_at": None,
                   "steps": [], "current": None, "index": 0,
                   "total": len(chain)})
    results: List[dict] = []
    error: Optional[str] = None
    try:
        if conn is None:
            conn = db.get_conn()
        _record(conn, run_id, started, "running", results)
        for index, (name, fn) in enumerate(chain, 1):
            _STATE.update({"current": name, "index": index,
                           "message": f"Step {index}/{len(chain)}: {name}"})
            began = time.monotonic()
            step_result: Dict[str, Any]
            try:
                value = fn()
                step_result = {"name": name, "ok": True,
                               "seconds": round(time.monotonic() - began, 2),
                               "result": value}
            except Exception as exc:
                step_result = {"name": name, "ok": False,
                               "seconds": round(time.monotonic() - began, 2),
                               "error": f"{type(exc).__name__}: {exc}",
                               "trace": traceback.format_exc()[-1500:]}
            results.append(step_result)
            _STATE["steps"] = results
            try:
                _record(conn, run_id, started, "running", results)
            except Exception:
                pass
        failed = [r["name"] for r in results if not r["ok"]]
        skipped = [r["name"] for r in results
                   if isinstance(r.get("result"), dict)
                   and r["result"].get("skipped")]
        status = "ok" if not failed else ("partial" if len(failed) < len(results)
                                          else "error")
        message = ("Refresh complete"
                   if status == "ok" else f"Refresh {status}: failed {failed}")
        _STATE.update({"running": False, "status": status,
                       "message": message,
                       "finished_at": now_ist().isoformat(timespec="seconds")})
        _record(conn, run_id, started, status, results, error)
        return {"ok": status == "ok", "status": status, "run_id": run_id,
                "failed": failed, "skipped": skipped,
                "seconds": sum(r.get("seconds", 0) for r in results),
                "steps": results, "message": message}
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        _STATE.update({"running": False, "status": "error",
                       "message": error, "finished_at":
                       now_ist().isoformat(timespec="seconds")})
        try:
            if conn is not None:
                _record(conn, run_id, started, "error", results, error)
        except Exception:
            pass
        return {"ok": False, "status": "error", "run_id": run_id,
                "error": error, "steps": results}
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        _LOCK.release()


def start_background(trigger: str = "ui",
                     include_detectors: bool = True) -> dict:
    """Start a refresh in a daemon thread; returns immediately."""
    if _STATE.get("running"):
        return {"started": False, "already_running": True,
                "state": status()}
    run_id = uuid.uuid4().hex[:12]
    thread = threading.Thread(
        target=run, kwargs={"trigger": trigger,
                            "include_detectors": include_detectors,
                            "run_id": run_id},
        name=f"refresh-{run_id}", daemon=True)
    thread.start()
    return {"started": True, "run_id": run_id, "state": status()}


def status(conn=None) -> dict:
    """Current in-memory state plus the latest persisted run."""
    out = dict(_STATE)
    latest = None
    own = conn is None
    try:
        conn = conn or db.get_conn()
        row = conn.execute(
            "SELECT run_id, started_at, finished_at, status, trigger, "
            "steps_json, error FROM refresh_runs "
            "ORDER BY started_at DESC LIMIT 1").fetchone()
        if row:
            latest = {"run_id": row[0], "started_at": row[1],
                      "finished_at": row[2], "status": row[3],
                      "trigger": row[4],
                      "steps": json.loads(row[5] or "[]"),
                      "error": row[6]}
    except Exception as exc:
        out["db_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    out["latest_run"] = latest
    return out


def health(conn=None) -> dict:
    """Everything a 'can I trust the data right now?' banner needs."""
    own = conn is None
    out: Dict[str, Any] = {"ok": False, "time": now_ist().isoformat(
        timespec="seconds")}
    try:
        conn = conn or db.get_conn()
        max_date = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
        rows = conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
        out.update({"prices_rows": rows, "max_price_date": max_date,
                    "gated": True})
        try:
            import freshness_gate
            gate = freshness_gate.assess(conn)
            out["freshness"] = gate
            out["gated"] = bool(gate.get("blocked"))
        except Exception as exc:
            out["freshness"] = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            import fyers_client
            store = fyers_client.TokenStore()
            out["fyers"] = {
                "token": store.status(),
                "pin_configured": bool(
                    __import__("os").environ.get("FYERS_PIN", "").strip()),
                "app_configured": bool(
                    __import__("os").environ.get("FYERS_APP_ID", "").strip()),
            }
        except Exception as exc:
            out["fyers"] = {"error": f"{type(exc).__name__}: {exc}"}
        today = now_ist().date().isoformat()
        artifacts = {}
        latest_dates = {}
        for table, column in (("technicals_daily", "date"),
                              ("scan_results", "scan_date"),
                              ("ml_predictions", "prediction_date"),
                              ("pattern_tags", "date"),
                              ("top_picks", "date")):
            try:
                latest = conn.execute(
                    f"SELECT MAX({column}) FROM {table}").fetchone()[0]
                latest_dates[table] = latest
                artifacts[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column}=?",
                    (latest,)).fetchone()[0] if latest else 0
            except Exception:
                artifacts[table] = None
                latest_dates[table] = None
        out["artifacts_today"] = artifacts
        out["artifacts_latest_dates"] = latest_dates
        out["ist_date"] = today
        out["last_refresh"] = status(conn).get("latest_run")
        try:
            import scheduler_bg
            out["scheduler"] = scheduler_bg.status()
        except Exception as exc:
            out["scheduler"] = {"error": f"{type(exc).__name__}: {exc}"}
        out["ok"] = (bool(max_date) and not out.get("gated"))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return out


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    child = sub.add_parser("run")
    child.add_argument("--skip-detectors", action="store_true",
                       help="skip patterns/templates (fast refresh)")
    child.add_argument("--trigger", default="cli")
    sub.add_parser("status")
    sub.add_parser("health")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        print(json.dumps(run(trigger=args.trigger,
                             include_detectors=not args.skip_detectors),
                         indent=2, default=str))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2, default=str))
    else:
        print(json.dumps(health(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
