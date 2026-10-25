"""Portal freshness guard: keep the price spine current before the UI reads it.

WHY THIS EXISTS
---------------
The scheduled EOD chain is not allowed to be the only line of defence. Twice
the system froze because a self-referential check said "nothing is stale" while
the whole market table was frozen. This module is the external reference and the
self-healing path:

* ``assess`` compares ``MAX(prices_daily.date)`` with the session that should
  exist now, in IST, not with the table's own maximum.
* ``ensure_fresh`` synchronously retries the official NSE archive for every
  missing weekday. This is fast (one CSV per day) and repairs the common case
  before the portal loads.
* If the official archive cannot fill the gap, it starts the existing
  ``refresh_pipeline`` in the background (Yahoo/Fyers fallback + all derived
  layers), so the page can load last-known data and auto-reload when done.
* A process-start hook and a scheduler watchdog call the same function, so a
  missed cron, a service restart, or a laptop sleep cannot leave the portal
  frozen indefinitely.

Only one guard runs at a time. The function never raises: a failure is returned
as a status dict so the UI can show an honest stale banner instead of a fake
"fresh" state.
"""
from __future__ import annotations

import datetime as dt
import threading
from typing import Any, Optional

import db
import freshness_gate
import nse_eod_ingest

IST = freshness_gate.IST
# The official evening file normally appears at 18:00-19:00 IST. Before that,
# a 404 for today is expected and must not be recorded as a holiday.
OFFICIAL_PUBLISH_AFTER = dt.time(18, 0)
DEFAULT_DAYS_BACK = 15
DEFAULT_LOCK_WAIT = 45.0

_RUN_LOCK = threading.Lock()
_STATE_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "running": False,
    "status": "idle",
    "message": "No freshness check has run yet.",
    "started_at": None,
    "finished_at": None,
    "last_result": None,
}


def _as_ist(now: Optional[dt.datetime]) -> dt.datetime:
    if now is None:
        return dt.datetime.now(IST)
    return now.replace(tzinfo=IST) if now.tzinfo is None else now.astimezone(IST)


def _previous_weekday(day: dt.date) -> dt.date:
    cursor = day - dt.timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= dt.timedelta(days=1)
    return cursor


def expected_session(now: Optional[dt.datetime] = None) -> dt.date:
    """The bar the portal should have now (close-aware, weekdays only)."""
    return freshness_gate.expected_session(now)


def official_expected_session(now: Optional[dt.datetime] = None) -> dt.date:
    """The latest date whose official NSE evening file should exist now."""
    moment = _as_ist(now)
    today = moment.date()
    if today.weekday() < 5 and moment.time() >= OFFICIAL_PUBLISH_AFTER:
        return today
    return _previous_weekday(today)


def _weekday_count(start: dt.date, end: dt.date) -> int:
    return freshness_gate._weekday_count(start, end)


def _latest_price_date(conn) -> Optional[dt.date]:
    row = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()
    text = str(row[0] or "").strip()[:10] if row else ""
    return dt.date.fromisoformat(text) if text else None


def _sync_window(conn, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    if start > end:
        return []
    rows = conn.execute(
        "SELECT date,status,rows,fetched_at,error FROM nse_eod_sync "
        "WHERE date>=? AND date<=? ORDER BY date",
        (start.isoformat(), end.isoformat())).fetchall()
    return [dict(zip(("date", "status", "rows", "fetched_at", "error"), row))
            for row in rows]


def assess(conn, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Return a strict, UI-ready freshness assessment. Never raises."""
    moment = _as_ist(now)
    expected = expected_session(moment)
    official_expected = official_expected_session(moment)
    out: dict[str, Any] = {
        "now": moment.isoformat(timespec="seconds"),
        "latest": None,
        "expected": expected.isoformat(),
        "official_expected": official_expected.isoformat(),
        "missing_sessions": 0,
        "missing_official": 0,
        "fresh": False,
        "needs_official": True,
        "needs_yahoo": True,
        "status": "empty",
        "message": "No prices are stored yet.",
        "sync": [],
    }
    try:
        latest = _latest_price_date(conn)
    except Exception as exc:
        out.update(status="error", message=f"cannot read prices: {exc}",
                   error=f"{type(exc).__name__}: {exc}")
        return out

    if latest is None:
        out["sync"] = _sync_window(conn, expected, expected)
        return out

    missing = _weekday_count(latest + dt.timedelta(days=1), expected)
    missing_official = _weekday_count(latest + dt.timedelta(days=1),
                                      official_expected)
    fresh = latest >= expected
    needs_official = latest < official_expected
    needs_yahoo = latest < expected
    status = "fresh" if fresh else (
        "awaiting_yahoo" if not needs_official else "stale")
    if fresh:
        message = f"Prices are current through {latest.isoformat()}."
    elif needs_official:
        message = (f"Prices are behind: latest {latest.isoformat()}, "
                   f"expected {expected.isoformat()}, "
                   f"{missing} session(s) missing.")
    else:
        message = (f"Official close {latest.isoformat()} is loaded; today's "
                   f"exchange bar is still pending.")

    out.update({
        "latest": latest.isoformat(),
        "missing_sessions": missing,
        "missing_official": missing_official,
        "fresh": fresh,
        "needs_official": needs_official,
        "needs_yahoo": needs_yahoo,
        "status": status,
        "message": message,
        "sync": _sync_window(conn, latest + dt.timedelta(days=1),
                             max(expected, official_expected)),
    })
    return out


def _set_state(**kw: Any) -> None:
    with _STATE_LOCK:
        _STATE.update(kw)


def _state_snapshot() -> dict[str, Any]:
    with _STATE_LOCK:
        return dict(_STATE)


def _compact_catch_up(result: Optional[dict]) -> Optional[dict]:
    """Keep the API response small; per-date details stay in nse_eod_sync."""
    if not result:
        return result
    return {key: result.get(key) for key in
            ("attempted", "ok", "missing", "errors", "pending_remaining")}


def ensure_fresh(days_back: int = DEFAULT_DAYS_BACK,
                 now: Optional[dt.datetime] = None,
                 start_background: bool = True,
                 force: bool = False,
                 lock_wait: float = DEFAULT_LOCK_WAIT,
                 conn=None) -> dict[str, Any]:
    """Check and repair the price spine. Safe to call from any request thread.

    ``start_background`` is True for portal requests and the startup hook; the
    scheduler watchdog can pass False when it only wants the official repair.
    """
    moment = _as_ist(now)
    acquired = _RUN_LOCK.acquire(timeout=max(0.0, float(lock_wait)))
    if not acquired:
        state = _state_snapshot()
        state.update({"running": True, "fresh": False,
                      "message": "Another freshness check is still running."})
        return state

    started = dt.datetime.now(IST).isoformat(timespec="seconds")
    _set_state(running=True, status="checking", started_at=started,
               finished_at=None, message="Checking price freshness.")
    own_conn = conn is None
    try:
        if own_conn:
            conn = db.get_conn()
        before = assess(conn, moment)
        official = None
        if force or not before["fresh"]:
            if force or before["needs_official"]:
                include_today = (
                    before["official_expected"] == moment.date().isoformat())
                official = nse_eod_ingest.catch_up(
                    conn,
                    days_back=max(10, int(days_back)),
                    include_today=include_today,
                    timeout=10,
                    max_seconds=25,
                )
        after = assess(conn, moment)
        repaired = bool(before.get("latest") != after.get("latest"))
        result: dict[str, Any] = dict(after)
        result.update({
            "before": before,
            "repaired": repaired,
            "official": _compact_catch_up(official),
            "guard": {"started_at": started},
        })

        if after["fresh"] and not repaired:
            message = after["message"]
            result["refresh"] = None
        elif after["fresh"]:
            message = (f"Repaired prices through {after['latest']}; "
                       f"recomputing derived data.")
            result["refresh"] = None
            if start_background:
                import refresh_pipeline
                result["refresh"] = refresh_pipeline.start_background(
                    trigger="freshness-repair")
        else:
            message = after["message"]
            result["refresh"] = None
            if start_background:
                import refresh_pipeline
                result["refresh"] = refresh_pipeline.start_background(
                    trigger="portal-open")
            if result.get("refresh"):
                message = (f"{after['message']} Full refresh "
                           f"{'started' if result['refresh'].get('started') else 'already running'}.")
        result["message"] = message
        _set_state(running=False,
                   status=("repaired" if repaired and after["fresh"]
                           else after["status"]),
                   message=message,
                   finished_at=dt.datetime.now(IST).isoformat(
                       timespec="seconds"),
                   last_result=result)
        return result
    except Exception as exc:
        message = f"Freshness repair failed: {type(exc).__name__}: {exc}"
        result = {
            "fresh": False, "status": "error", "message": message,
            "error": f"{type(exc).__name__}: {exc}",
            "now": moment.isoformat(timespec="seconds"),
        }
        _set_state(running=False, status="error", message=message,
                   finished_at=dt.datetime.now(IST).isoformat(
                       timespec="seconds"),
                   last_result=result)
        return result
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        _RUN_LOCK.release()


def status(conn=None, now: Optional[dt.datetime] = None) -> dict[str, Any]:
    """Assessment plus the guard's in-memory state, for the UI/diagnostics."""
    own = conn is None
    try:
        conn = conn or db.get_conn()
        out = assess(conn, now)
    except Exception as exc:
        out = {"fresh": False, "status": "error",
               "message": f"{type(exc).__name__}: {exc}"}
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    state = _state_snapshot()
    out["guard"] = state
    out["running"] = state.get("running", False)
    return out


def main(argv=None) -> int:
    import json
    result = ensure_fresh(start_background=False)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("fresh") else 2


if __name__ == "__main__":
    raise SystemExit(main())
