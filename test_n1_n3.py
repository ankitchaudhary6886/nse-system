"""Regression tests for N1 (scan the whole band) and N3 (month-by-month ledger).

Runs on the laptop and on the VM: every assertion is about internal
consistency, never about hardcoded counts, because the two machines hold
different data (see PROJECT_HANDOFF §4.9).

Run it with the project venv:
    .\\env\\Scripts\\python.exe test_n1_n3.py
"""
import sqlite3
import sys

import scheduler_bg

# Never let a test run touch the live scheduler (no cron job, no Telegram).
scheduler_bg.start = lambda *a, **k: None
scheduler_bg.stop = lambda *a, **k: None

from fastapi.testclient import TestClient

import db
import ledger
import screener_engine
import terminal_api
import universe_helper as U

FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _fresh_db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE swing_signals (signal_date TEXT, symbol TEXT, "
              "entry_trigger REAL, stop REAL, target REAL, outcome TEXT)")
    return c


def test_ledger_math():
    print("\n--- ledger: overall vs monthly ---")
    empty = _fresh_db()
    check("empty DB -> None", ledger.compute_stats(empty) is None)
    check("empty DB -> []", ledger.compute_monthly_stats(empty) == [])

    e = _fresh_db()
    e.execute("INSERT INTO swing_signals VALUES ('2026-01-05','AAA',100,100,120,'WIN')")
    e.execute("INSERT INTO swing_signals VALUES ('2026-01-06','BBB',100,95,120,'EXPIRED')")
    e.execute("INSERT INTO swing_signals VALUES ('2026-01-07','CCC',NULL,95,120,'WIN')")
    e.execute("INSERT INTO swing_signals VALUES ('2026-01-08','DDD',100,95,120,'LOSS')")
    e.execute("INSERT INTO swing_signals VALUES ('bad-date','EEE',200,190,240,'LOSS')")
    s, m = ledger.compute_stats(e), ledger.compute_monthly_stats(e)
    check("only real trades counted", s and s["total_trades"] == 2, str(s))
    check("unreadable date kept, not dropped",
          sum(r["total_trades"] for r in m) == s["total_trades"], str([r["month"] for r in m]))
    check("unreadable date labelled Unknown, shown last",
          m[-1]["month"] == ledger.UNKNOWN_MONTH and m[-1]["total_trades"] == 1,
          str([r["month"] for r in m]))

    live = ledger.compute_stats()
    months = ledger.compute_monthly_stats()
    if live is None:
        check("live DB has no graded trades (nothing to reconcile)", True)
        return
    check("monthly trades reconcile with overall",
          sum(x["total_trades"] for x in months) == live["total_trades"])
    check("monthly wins/losses reconcile",
          sum(x["wins"] for x in months) == live["wins"]
          and sum(x["losses"] for x in months) == live["losses"])
    check("monthly R reconciles (allow 1 paisa/month rounding)",
          abs(sum(x["total_r"] for x in months) - live["total_r"]) < 0.01 * len(months) + 0.001)
    known = [x["month"] for x in months if x["month"] != ledger.UNKNOWN_MONTH]
    check("newest month first", known == sorted(known, reverse=True))
    check("limit_months respected", len(ledger.compute_monthly_stats(limit_months=1)) <= 2)


def test_band_scan_engine():
    print("\n--- screener: band scan engine ---")
    calls = []
    screener_engine.screen_universe(
        limit=6, show=False,
        progress=lambda done, total, hits: calls.append((done, total, hits)))
    check("progress fires once per symbol", len(calls) == 6, str(len(calls)))
    check("progress counts 1..N in order", [c[0] for c in calls] == list(range(1, 7)))
    check("progress reports the right total", all(c[1] == 6 for c in calls))

    hits = screener_engine.screen_universe(limit=6, show=False,
                                          progress=lambda *a: 1 / 0)
    check("a broken progress callback cannot abort a scan", isinstance(hits, list))

    orig = screener_engine.evaluate_stock
    screener_engine.evaluate_stock = (
        lambda sym, allow_yahoo=False: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        hits = screener_engine.screen_universe(limit=6, show=False)
        check("one exploding symbol cannot abort a scan", isinstance(hits, list))
    finally:
        screener_engine.evaluate_stock = orig


def test_endpoints():
    print("\n--- endpoints ---")
    conn = db.get_conn()
    band = U.band_universe(conn, None)
    conn.close()

    with TestClient(terminal_api.app) as c:
        r = c.get("/api/ledger/monthly")
        check("/api/ledger/monthly 200", r.status_code == 200)
        check("/api/ledger/monthly returns months list",
              isinstance(r.json().get("months"), list))
        check("/api/ledger/monthly?months=0 does not crash", c.get("/api/ledger/monthly?months=0").status_code == 200)
        check("/api/ledger/monthly?months=9999 does not crash", c.get("/api/ledger/monthly?months=9999").status_code == 200)

        r = c.get("/api/screener/scan?limit=10")
        check("quick /api/screener/scan still works", r.json().get("scanned") == 10,
              str(r.json().get("scanned")))

        st = c.get("/api/screener/scan-universe/status").json()
        check("band scan starts idle", st["running"] is False and st["status"] == "idle")

        started = c.post("/api/screener/scan-universe").json()
        check("band scan starts", started.get("started") is True, str(started))

        st = c.get("/api/screener/scan-universe/status").json()
        check("band scan completes", st["running"] is False and st["status"] == "complete", st["status"])
        check("band scan walked the whole band", st["total"] == len(band) and st["scanned"] == len(band),
              f'{st["scanned"]}/{st["total"]} vs {len(band)} in the band')
        check("hits is a list and count agrees",
              isinstance(st["hits"], list) and st["hits_count"] == len(st["hits"]))
        if st["hits"]:
            h = st["hits"][0]
            check("a hit carries the fields the table shows",
                  all(k in h for k in ("ticker", "current_price", "momentum_1m",
                                       "pullback_depth", "tightness_pct")))
            check("a hit really passed the checks", h.get("overall_signal") is True)

        with terminal_api._BAND_SCAN_LOCK:
            terminal_api._BAND_SCAN_STATE["running"] = True
        check("a second scan is refused while one runs",
              c.post("/api/screener/scan-universe").json().get("already_running") is True)
        with terminal_api._BAND_SCAN_LOCK:
            terminal_api._BAND_SCAN_STATE["running"] = False

        html = c.get("/").text
        for needle in ("runBandScanBtn", "bandScanResults", "ledgerMonthlyTable"):
            check(f"page serves {needle}", needle in html)
        js = c.get("/static/app.js").text
        for needle in ("startBandScan", "renderBandHits", "loadLedgerMonthly",
                       "/api/screener/scan-universe", "/api/ledger/monthly"):
            check(f"app.js wires {needle}", needle in js)


if __name__ == "__main__":
    test_ledger_math()
    test_band_scan_engine()
    test_endpoints()
    print("\n" + "=" * 60)
    if FAILS:
        print(f"{len(FAILS)} CHECK(S) FAILED:")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("ALL N1 + N3 TESTS PASSED")
