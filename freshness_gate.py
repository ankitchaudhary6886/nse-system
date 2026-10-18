"""Hard freshness gate: signal writers must not publish on a stale price spine.

Why this exists
---------------
The price ingest stopped advancing ``prices_daily`` on 2026-08-27. Nothing
failed loudly: ``data_quality.py`` only *alerts*, so the pattern, template and
institutional writers kept reading the frozen spine and published artifacts
dated 2026-10-07 - six weeks of signals derived from bars that never existed.
Alerts are advisory; this module is the enforcement layer. A writer calls
:func:`require_fresh` before writing and refuses for the night when the price
spine has stopped advancing.

Freshness model
---------------
* IST is UTC+5:30 and every date/time decision uses aware IST datetimes.
* The cash market closes at 15:40 IST, so a bar for *today* is only expected
  from 15:40 onwards on a weekday.
* ``expected_session`` = today when it is a weekday at or past the close,
  otherwise the most recent *previous* weekday (a Saturday expects Friday, a
  Monday pre-open expects Friday too).
* ``missing_sessions`` counts weekdays from ``max_price_date + 1`` through
  ``expected_session`` inclusive. Exchange holidays are not modelled here; the
  session threshold absorbs them.
* ``calendar_days_stale`` = ``(now.date() - max_price_date).days``, a wall-clock
  backstop that does not depend on the session count.
* Blocked when there is no price spine, when ``missing_sessions`` reaches
  ``threshold_sessions``, or when ``calendar_days_stale`` exceeds
  ``threshold_calendar_days``.

Thresholds
----------
``FRESHNESS_BLOCK_SESSIONS`` (default 2): one missed weekday is tolerated - a
single gap is indistinguishable from a single exchange holiday, and the pipeline
may simply be running before the EOD ingest; two *consecutive* missed weekdays
cannot both be holidays, so the spine is stale. ``FRESHNESS_MAX_STALE_DAYS``
(default 7) backstops staleness the session count cannot express.

Fail-safe
---------
Uncertainty never writes. :func:`assess` never raises: when it cannot read the
price spine it returns ``blocked=True`` with reason ``"cannot determine
freshness"``. :func:`require_fresh` also refuses when its audit row cannot be
written, so a broken database is never mistaken for fresh data. The audit table
``freshness_gate_log`` is owned by ``db.SCHEMA``; this module never creates it
and never opens a connection at import time.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys
from typing import Any

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MARKET_CLOSE = dt.time(15, 40)  # NSE cash close
DEFAULT_BLOCK_SESSIONS = 2
DEFAULT_MAX_STALE_DAYS = 7
ENV_BLOCK_SESSIONS = "FRESHNESS_BLOCK_SESSIONS"
ENV_MAX_STALE_DAYS = "FRESHNESS_MAX_STALE_DAYS"
FAILSAFE_REASON = "cannot determine freshness"
LOG_TABLE = "freshness_gate_log"
LOG_COLUMNS = ("run_at, artifact, status, max_price_date, expected_date, "
               "stale_sessions, action, detail")


def now_ist() -> dt.datetime:
    """Current time as a timezone-aware IST datetime."""
    return dt.datetime.now(tz=IST)


def _as_ist(now: dt.datetime | None) -> dt.datetime:
    """Normalise ``now`` to aware IST; naive input is read as IST wall clock."""
    if now is None:
        return now_ist()
    return now.replace(tzinfo=IST) if now.tzinfo is None else now.astimezone(IST)


def _parse_date(value: Any) -> dt.date | None:
    """Parse a stored 'YYYY-MM-DD[...]' cell; None when absent or unusable."""
    text = str(value).strip()[:10] if value is not None else ""
    return dt.date.fromisoformat(text) if text else None


def _previous_weekday(day: dt.date) -> dt.date:
    cursor = day - dt.timedelta(days=1)
    while cursor.weekday() >= 5:  # Saturday=5, Sunday=6
        cursor -= dt.timedelta(days=1)
    return cursor


def expected_session(now: dt.datetime | None = None) -> dt.date:
    """Session whose bar the price spine should already hold.

    Today counts only after the 15:40 IST close on a weekday; at any other
    moment (weekend, pre-close run) the most recent previous weekday is
    expected, because no bar for today can exist yet.
    """
    moment = _as_ist(now)
    today = moment.date()
    if today.weekday() < 5 and moment.time() >= MARKET_CLOSE:
        return today
    return _previous_weekday(today)


def _weekday_count(start: dt.date, end: dt.date) -> int:
    """Number of Mon-Fri calendar dates in ``start..end`` inclusive."""
    if start > end:
        return 0
    weeks, remainder = divmod((end - start).days + 1, 7)
    return weeks * 5 + sum(
        1 for offset in range(remainder)
        if (start.weekday() + offset) % 7 < 5)


def _int_env(name: str, default: int) -> int:
    """Read an integer threshold >= 1; missing or invalid input uses default."""
    try:
        value = int(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value >= 1 else default


def _max_price_date(conn: sqlite3.Connection) -> dt.date | None:
    """Latest date present in ``prices_daily``; None when the spine is empty."""
    row = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()
    return _parse_date(row[0] if row else None)


def assess(conn: sqlite3.Connection,
           now: dt.datetime | None = None) -> dict[str, Any]:
    """Decide whether the price spine is current enough to write signals from.

    Pure read: never writes and never raises. ``blocked`` is the decision and
    ``reason`` is a one-sentence explanation fit for logs and alerts. When the
    spine cannot be read the result stays blocked with ``error`` set.
    """
    moment = _as_ist(now)
    today = moment.date()
    market_closed = today.weekday() < 5 and moment.time() >= MARKET_CLOSE
    expected = expected_session(moment)
    threshold_sessions = _int_env(ENV_BLOCK_SESSIONS, DEFAULT_BLOCK_SESSIONS)
    threshold_days = _int_env(ENV_MAX_STALE_DAYS, DEFAULT_MAX_STALE_DAYS)

    result: dict[str, Any] = {
        "now": moment.isoformat(timespec="seconds"),
        "max_price_date": None,
        "expected_session": expected.isoformat(),
        "missing_sessions": 0,
        "calendar_days_stale": 0,
        "blocked": True,
        "reason": FAILSAFE_REASON,
        "market_closed": market_closed,
        "threshold_sessions": threshold_sessions,
        "threshold_calendar_days": threshold_days,
    }

    try:
        max_date = _max_price_date(conn)
    except Exception as exc:  # the gate must never raise; stay blocked instead
        result["error"] = f"cannot read prices_daily: {exc}"
        return result

    if max_date is None:
        result["reason"] = ("BLOCKED: prices_daily holds no price rows - there "
                            "is no price spine to derive signals from")
        return result

    missing = _weekday_count(max_date + dt.timedelta(days=1), expected)
    stale_days = (today - max_date).days
    result.update({
        "max_price_date": max_date.isoformat(),
        "missing_sessions": missing,
        "calendar_days_stale": stale_days,
    })

    causes = []
    if missing >= threshold_sessions:
        causes.append(f"{missing} weekday session(s) missing after {max_date} "
                      f"(expected {expected}, threshold {threshold_sessions})")
    if stale_days > threshold_days:
        causes.append(f"{stale_days} calendar days stale vs {today} "
                      f"(threshold {threshold_days})")
    if causes:
        result["reason"] = "BLOCKED: " + "; ".join(causes)
        return result

    result["blocked"] = False
    if missing:
        result["reason"] = (
            f"OK: {missing} weekday session(s) missing after {max_date} "
            f"(expected {expected}) is tolerated - one gap can be an exchange "
            f"holiday or a run ahead of the EOD ingest, threshold is "
            f"{threshold_sessions}")
    else:
        result["reason"] = (f"OK: latest bar {max_date} covers expected "
                            f"session {expected}")
    return result


def require_fresh(conn: sqlite3.Connection, artifact: str,
                  now: dt.datetime | None = None) -> dict[str, Any]:
    """Gate entry point for a signal writer: assess, audit, then allow/refuse.

    Appends exactly one row to ``freshness_gate_log`` per call (status ``OK`` +
    action ``proceed``, or status ``BLOCKED`` + action ``refuse``) and returns
    the assessment enriched with ``artifact``, ``status`` and ``action``.
    Never raises: if freshness cannot be determined, or the audit row cannot be
    written, the result is ``blocked=True`` with reason
    ``"cannot determine freshness"`` - treat that as a refusal.
    """
    moment = _as_ist(now)
    result = assess(conn, now=moment)

    status_text = "BLOCKED" if result["blocked"] else "OK"
    action = "refuse" if result["blocked"] else "proceed"
    row = (moment.isoformat(timespec="seconds"), str(artifact), status_text,
           result.get("max_price_date"), result.get("expected_session"),
           int(result.get("missing_sessions") or 0), action,
           str(result.get("reason") or ""))
    try:
        conn.execute(
            f"INSERT INTO {LOG_TABLE} ({LOG_COLUMNS}) VALUES (?,?,?,?,?,?,?,?)",
            row)
        conn.commit()
    except Exception as exc:  # audit failed -> do not let the writer proceed
        failed = dict(result)
        failed.update({"artifact": str(artifact), "status": "BLOCKED",
                       "action": "refuse", "blocked": True,
                       "reason": FAILSAFE_REASON,
                       "error": f"cannot write {LOG_TABLE}: {exc}"})
        return failed

    result["artifact"] = str(artifact)
    result["status"] = status_text
    result["action"] = action
    return result


def status(conn: sqlite3.Connection,
           now: dt.datetime | None = None) -> dict[str, Any]:
    """Diagnostics: current assessment plus the last 10 gate decisions.

    Assessment fields sit at the top level; ``recent_log`` holds the tail of
    ``freshness_gate_log`` across every artifact, newest first.
    """
    result = dict(assess(conn, now=now))
    try:
        rows = conn.execute(
            f"SELECT {LOG_COLUMNS} FROM {LOG_TABLE} ORDER BY rowid DESC LIMIT 10"
        ).fetchall()
        keys = [name.strip() for name in LOG_COLUMNS.split(",")]
        result["recent_log"] = [dict(zip(keys, row)) for row in rows]
    except Exception as exc:
        result["recent_log"] = []
        result["log_error"] = str(exc)
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI: ``status`` prints diagnostics, ``check`` exits 2 when blocked.

    The connection is opened lazily here and closed again, so importing this
    module never touches the database.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0].strip().lower() if args else "status"
    if command not in ("status", "check"):
        print(json.dumps({"error": f"unknown command {command!r}; "
                                   "use 'status' or 'check'"}, indent=2))
        return 1

    import db  # lazy: importing this module must not open the database

    conn = db.get_conn()
    try:
        if command == "check":
            result = assess(conn)
            print(json.dumps(result, indent=2, default=str))
            return 2 if result["blocked"] else 0
        print(json.dumps(status(conn), indent=2, default=str))
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
