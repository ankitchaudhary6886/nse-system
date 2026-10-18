"""Hard freshness gate adapter for signal writers (Option A, 2026-10-18).

WHY THIS EXISTS
---------------
The price store was frozen on 2026-08-27 while pattern/template/institutional
writers still produced artifacts dated 2026-10-07. `data_quality.py` only
alerts; it never stopped a writer. The owner approved a HARD block: when the
price spine is stale, signal writers must refuse to write rather than produce
artifacts that look current but are computed from old bars.

DESIGN
- `check(conn, artifact)` returns True when the writer must refuse.
- The heavy lifting lives in `freshness_gate.py` (`require_fresh`), which also
  appends an audit row to `freshness_gate_log` for every decision.
- Fail-safe: if the gate exists but raises, the writer refuses (True). A gate
  we cannot evaluate must not silently allow writing.
- During a partial deployment where `freshness_gate.py` is missing, the guard
  allows the writer (False) so the pipeline keeps working until the gate ships.

Usage in a writer (before any write):

    if signal_guard.check(conn, "patterns"):
        conn.close()
        return {...}

Every call is cheap: one MAX(date) query plus a log insert.
"""
from __future__ import annotations


def check(conn, artifact: str) -> bool:
    """True = stale data, refuse to write. Never raises, never writes signals."""
    try:
        import freshness_gate
    except Exception:
        # Gate not deployed yet: keep the pipeline alive (documented above).
        return False
    try:
        decision = freshness_gate.require_fresh(conn, artifact)
    except Exception as exc:  # fail-safe: cannot evaluate -> refuse
        print(f"[{artifact}] HARD-BLOCKED — freshness gate error: "
              f"{type(exc).__name__}: {exc}")
        return True
    if decision.get("blocked"):
        reason = decision.get("reason") or "stale price data"
        print(f"[{artifact}] HARD-BLOCKED — {reason}")
        print(f"[{artifact}] nothing written. Fix the price ingest, then re-run.")
        return True
    return False
