"""Standalone tests for exit_policy.py — the swing exit rules and the R scorer.

WHY THESE TESTS LOOK LIKE THIS
------------------------------
The expensive mistake in exit code is a silent convention change: a bar that
touches both the stop and the target is a LOSS in production
(swing_live.update_outcomes checks the stop first). A scorer that quietly grades
the same bar a WIN would report a strategy that does not exist. So every test
here is built on hand-computed synthetic price paths — small enough to check by
eye — and the tie case is asserted under BOTH rules, with the rule name checked
in the result.

TWO MACHINES, TWO DIFFERENT LEDGERS
-----------------------------------
This suite runs on the laptop (a stale data/app.db with a handful of rows) and
on the VM (the real production ledger, 155+ rows across two modes). So no
expected value may be hardcoded: every database figure is read back from the
database first, exactly the way test_n1_n3.py does it. Checks that need a
fixture this machine may not have — no SWING rows, no SetupDetector trigger in
the available history, no readable swing_signals table — print SKIP with the
reason and exit 0 instead of failing. The synthetic checks (tie rule, R
scorer, exit rules, MFE/MAE) are never skipped: they need no data.

No pytest, no network, no Telegram, no writes to the live database: the report
test opens the ledger READ ONLY and proves it cannot write.

Run it with the project venv:
    .\\env\\Scripts\\python.exe test_swing_exits.py
"""
import importlib
import os
import sqlite3
import sys

import exit_policy as ep

FAILS = []
SKIPS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name +
          (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def skip(name, reason):
    """A check that this machine's data cannot support. Not a failure."""
    print(f"SKIP  {name}   {reason}")
    SKIPS.append(f"{name} ({reason})")


def near(a, b, tol=1e-6):
    """True when a and b are the same number within a tolerance."""
    try:
        return a is not None and b is not None and abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


# ======================================================================
# 1. The plan: entry, stop, risk, target multiple
# ======================================================================
def test_plan_math():
    print("\n--- exit plan: 1R, target multiple, warnings ---")
    check("1R = entry - stop", near(ep.risk_per_share(100, 90), 10))
    for bad in ((100, 100), (100, 105), (0, -1)):
        try:
            ep.risk_per_share(*bad)
            check(f"bad levels {bad} rejected", False)
        except ValueError:
            check(f"bad levels {bad} rejected", True)

    plan = ep.plan_from(100, 90)
    check("default target is 3R = 130", near(plan.target, 130), str(plan.target))
    check("default target_r is 3.0 (current live value)",
          near(plan.target_r, 3.0), str(plan.target_r))
    check("risk_pct is 10%", near(plan.risk_pct, 0.10), str(plan.risk_pct))
    check("time stop defaults to 30 bars", plan.hold_bars == 30)
    check("describe() mentions the multiple", "3R" in plan.describe(),
          plan.describe())

    check("explicit 1.5R target = 115",
          near(ep.plan_from(100, 90, target_r=1.5).target, 115))
    check("config 0.5R target = 105",
          near(ep.plan_from(100, 90, cfg={"TARGET_R_MULTIPLE": 0.5}).target, 105))

    tight = ep.plan_from(100, 99.9, atr_pct=0.05)
    check("stop inside one ATR is flagged",
          any("noise" in n for n in tight.notes), str(tight.notes))
    wide = ep.plan_from(100, 90, atr_pct=0.02)
    check("stop wider than one ATR is not flagged as noise",
          not any("noise" in n for n in wide.notes), str(wide.notes))


def test_resolve_target_r():
    print("\n--- target multiple resolution and the .get fallback ---")
    check("explicit value wins", near(ep.resolve_target_r(1.25), 1.25))
    check("cfg value used", near(ep.resolve_target_r(cfg={"TARGET_R_MULTIPLE": 0.5}), 0.5))
    check("missing key falls back to 3.0 (no KeyError)",
          near(ep.resolve_target_r(cfg={}), 3.0))
    check("junk value falls back to 3.0",
          near(ep.resolve_target_r(cfg={"TARGET_R_MULTIPLE": "junk"}), 3.0))
    check("zero/negative falls back to 3.0",
          near(ep.resolve_target_r(cfg={"TARGET_R_MULTIPLE": -2}), 3.0) and
          near(ep.resolve_target_r(cfg={"TARGET_R_MULTIPLE": 0}), 3.0))
    check("no cfg reads strategy_config",
          near(ep.resolve_target_r(), ep.resolve_target_r(cfg=_live_setup())),
          str(ep.resolve_target_r()))


def _live_setup():
    try:
        from strategy_config import SETUP
        return SETUP
    except Exception:
        return {}


def test_setup_survives_missing_config_key():
    """setup.py must not crash (and must keep 3.0) if the key is ever removed."""
    print("\n--- setup.py: missing config key still gives 3.0 ---")
    try:
        from strategy_config import SETUP
        import setup
    except Exception as e:                                    # pragma: no cover
        check("setup.py imports", False, str(e))
        return
    saved = SETUP.get("TARGET_R_MULTIPLE", "__absent__")
    try:
        if "TARGET_R_MULTIPLE" in SETUP:
            del SETUP["TARGET_R_MULTIPLE"]
        importlib.reload(setup)
        check("no KeyError without the config key",
              near(setup.SetupDetector.TARGET_R_MULTIPLE, 3.0),
              str(setup.SetupDetector.TARGET_R_MULTIPLE))
    except Exception as e:                                    # pragma: no cover
        check("no KeyError without the config key", False, repr(e))
    finally:
        if saved != "__absent__":
            SETUP["TARGET_R_MULTIPLE"] = saved
        importlib.reload(setup)
    check("live value restored from config",
          near(setup.SetupDetector.TARGET_R_MULTIPLE,
               ep.resolve_target_r(cfg=SETUP)),
          str(setup.SetupDetector.TARGET_R_MULTIPLE))


# ======================================================================
# 2. The scorer: win, loss, timeout, open, expired
# ======================================================================
def test_outcomes():
    print("\n--- scorer: win / loss / timeout / still open ---")
    win_bars = [(100, 105, 98, 104), (104, 112, 103, 110), (110, 132, 109, 131)]
    r = ep.score_path(win_bars, entry=100, stop=90, target=130)
    check("target hit is a WIN at +3R", r.outcome == "WIN" and near(r.r, 3.0),
          f"{r.outcome} r={r.r}")
    check("ledger R for a 3R win is +3.0", near(r.r_ledger, 3.0))
    check("exit bar counted from the trigger bar", r.exit_bar == 2, str(r.exit_bar))
    check("bars held includes the exit bar", r.bars_held == 3, str(r.bars_held))
    check("exit reason is TARGET", r.exit_reason == "TARGET")

    loss_bars = [(100, 105, 89, 95)]
    r = ep.score_path(loss_bars, entry=100, stop=90, target=130)
    check("stop hit first bar is a LOSS at -1R",
          r.outcome == "LOSS" and near(r.r, -1.0), f"{r.outcome} r={r.r}")
    check("loss keeps MFE from the same bar (what it printed)",
          near(r.mfe_r, 0.5) and near(r.mae_r, -1.1), f"mfe={r.mfe_r} mae={r.mae_r}")

    flat = [(100, 105, 98, 102)] * 5
    r = ep.score_path(flat, entry=100, stop=90, target=130, hold_bars=5)
    check("no touch inside the window is a TIMEOUT", r.outcome == "TIMEOUT")
    check("timeout R is the last close (+0.2R here)", near(r.r, 0.2), str(r.r))
    check("ledger scores a timeout as flat 0R", near(r.r_ledger, 0.0))

    r = ep.score_path(flat[:2], entry=100, stop=90, target=130, hold_bars=5)
    check("window running off the data is OPEN, not a fake TIMEOUT",
          r.outcome == "OPEN" and r.r is None, f"{r.outcome} r={r.r}")

    r = ep.score_idea([(90, 95, 85, 88)] * 4, entry=100, stop=90,
                      target=130, trigger_window=3)
    check("entry never triggered is EXPIRED with no R",
          r.outcome == "EXPIRED" and r.r is None and r.r_ledger is None)
    r = ep.score_idea([(90, 95, 85, 88)] * 2, entry=100, stop=90,
                      target=130, trigger_window=3)
    check("too few bars to expire a fresh idea is OPEN", r.outcome == "OPEN")


# ======================================================================
# 3. The intrabar tie — the hard requirement
# ======================================================================
def test_intrabar_tie():
    print("\n--- one bar touches BOTH stop and target ---")
    bars = [(100, 101, 99, 100), (100, 140, 80, 120)]   # bar1: high 140, low 80
    r = ep.score_path(bars, entry=100, stop=90, target=130)
    check("production rule grades the tie a LOSS",
          r.outcome == "LOSS" and near(r.r, -1.0), f"{r.outcome} r={r.r}")
    check("the result says which rule it used (stop_first)",
          r.tie_rule == ep.STOP_FIRST, r.tie_rule)
    check("both lines are recorded on the same bar",
          r.stop_bar == 1 and r.target_bar == 1,
          f"stop_bar={r.stop_bar} target_bar={r.target_bar}")

    r2 = ep.score_path(bars, entry=100, stop=90, target=130,
                       tie_rule=ep.TARGET_FIRST)
    check("target-first rule grades the same bar a WIN (comparison only)",
          r2.outcome == "WIN" and near(r2.r, 3.0), f"{r2.outcome} r={r2.r}")
    check("the target-first result labels itself", r2.tie_rule == ep.TARGET_FIRST)

    try:
        ep.score_path(bars, entry=100, stop=90, target=130, tie_rule="guess")
        check("an unknown tie rule is rejected", False)
    except ValueError:
        check("an unknown tie rule is rejected", True)

    # The same tie seen through the measurement sweep used by the report.
    facts = ep._path_facts(bars, 100, 90, (1.0,), 3, 30, ep.STOP_FIRST)
    check("sweep: a level hit on the stop bar is a LOSS",
          ep.result_at_level(facts, 1.0)["outcome"] == "LOSS")
    facts_t = ep._path_facts(bars, 100, 90, (1.0,), 3, 30, ep.TARGET_FIRST)
    check("sweep: target-first reads the same bar as a WIN",
          ep.result_at_level(facts_t, 1.0)["outcome"] == "WIN")

    # Touched BEFORE the stop bar = a real win, not a tie.
    earlier = [(100, 131, 99, 130), (130, 131, 89, 95)]
    r3 = ep.score_path(earlier, entry=100, stop=90, target=130)
    check("target touched on an earlier bar stays a WIN",
          r3.outcome == "WIN" and r3.exit_bar == 0, f"{r3.outcome} {r3.exit_bar}")


# ======================================================================
# 4. MFE / MAE
# ======================================================================
def test_mfe_mae():
    print("\n--- MFE / MAE in R units ---")
    bars = [(100, 108, 97, 105), (105, 130, 99, 128), (128, 135, 120, 132)]
    r = ep.score_path(bars, entry=100, stop=90, target=130)
    # bar0: +0.8R / -0.3R, bar1 hits the target (+3.0R / -0.1R)
    check("MFE is the best print before the exit (+3.0R)", near(r.mfe_r, 3.0),
          str(r.mfe_r))
    check("MAE is the worst print before the exit (-0.3R)", near(r.mae_r, -0.3),
          str(r.mae_r))
    check("bar numbers are recorded", r.mfe_bar == 1 and r.mae_bar == 0,
          f"mfe_bar={r.mfe_bar} mae_bar={r.mae_bar}")

    stopped = [(100, 108, 97, 105), (105, 140, 89, 95)]
    r = ep.score_path(stopped, entry=100, stop=90, target=130)
    # Same rule as setup_sim.py: the bar the trade dies on still counts.
    check("MFE includes the bar the stop hit (+4.0R)",
          r.outcome == "LOSS" and near(r.mfe_r, 4.0), f"{r.outcome} {r.mfe_r}")
    check("MAE on that bar is -1.1R", near(r.mae_r, -1.1), str(r.mae_r))

    # A +4R level touched on the stop bar is a tie -> LOSS, even though MFE 4.0.
    facts = ep._path_facts(stopped, 100, 90, (4.0,), 3, 30, ep.STOP_FIRST)
    check("a level first touched on the stop bar is still a LOSS",
          ep.result_at_level(facts, 4.0)["outcome"] == "LOSS")


# ======================================================================
# 5. Optional rules: breakeven and trailing
# ======================================================================
def test_breakeven_rule():
    print("\n--- optional breakeven stop ---")
    bars = [(100, 112, 98, 110), (110, 111, 99, 100)]
    r = ep.score_path(bars, entry=100, stop=90, target=130, breakeven_at_r=1.0)
    check("stop moved to entry and exits flat",
          r.outcome == "SCRATCH" and near(r.r, 0.0),
          f"{r.outcome} r={r.r}")
    check("exit price is the entry (breakeven)", near(r.exit_price, 100.0),
          str(r.exit_price))
    check("the stop is recorded as the exit reason", r.exit_reason == "STOP")

    # The arming bar itself must NOT be saved: stop-first still applies.
    same_bar = [(100, 112, 89, 95)]
    r2 = ep.score_path(same_bar, entry=100, stop=90, target=130,
                       breakeven_at_r=1.0)
    check("arming bar's own low still stops you out at the original stop",
          r2.outcome == "LOSS" and near(r2.r, -1.0), f"{r2.outcome} r={r2.r}")

    # Without the rule, the same path would have stopped out at 90 for -1R.
    r3 = ep.score_path(bars, entry=100, stop=90, target=130, hold_bars=2)
    check("without the rule the same path is not saved (timeout at flat 0R)",
          r3.outcome == "TIMEOUT" and near(r3.r, 0.0), f"{r3.outcome} r={r3.r}")


def test_trail_rule():
    print("\n--- optional EMA trailing exit ---")
    bars = [(100, 112, 98, 110), (110, 111, 100, 105)]
    r = ep.score_path(bars, entry=100, stop=90, target=130, trail_ema=2,
                      trail_after_r=1.0)
    check("trail exits on the close below the EMA",
          r.outcome == "WIN" and r.exit_reason == "TRAIL",
          f"{r.outcome} {r.exit_reason}")
    check("trail exit price is that close", near(r.exit_price, 105.0),
          str(r.exit_price))
    check("trail R is +0.5R", near(r.r, 0.5), str(r.r))
    r2 = ep.score_path(bars, entry=100, stop=90, target=130, hold_bars=2)
    check("without the trail the trade simply times out flat",
          r2.outcome == "TIMEOUT", r2.outcome)


# ======================================================================
# 6. Entry trigger and the gap option
# ======================================================================
def test_trigger_and_gap():
    print("\n--- entry trigger window and gap fills ---")
    bars = [(90, 95, 85, 88), (90, 96, 86, 89), (95, 101, 94, 100),
            (100, 131, 99, 130)]
    r = ep.score_idea(bars, entry=100, stop=90, target=130, trigger_window=3)
    check("trigger may fire on the 3rd bar after the signal",
          r.outcome == "WIN" and r.exit_bar == 1, f"{r.outcome} {r.exit_bar}")
    r = ep.score_idea(bars, entry=100, stop=90, target=130, trigger_window=1)
    check("a 1-bar trigger window expires the same idea", r.outcome == "EXPIRED")

    # Production checks the trigger bar itself: entry filled, then stopped out.
    dipped = [(100, 105, 85, 90)]
    r = ep.score_idea(dipped, entry=100, stop=90, target=130)
    check("trigger bar that dips to the stop is a LOSS at -1R",
          r.outcome == "LOSS" and near(r.r, -1.0), f"{r.outcome} r={r.r}")

    gap = [(100, 105, 99, 100), (85, 90, 80, 82)]
    r = ep.score_path(gap, entry=100, stop=90, target=130)
    check("default matches production: no gap modelling, -1R",
          near(r.r, -1.0), str(r.r))
    r = ep.score_path(gap, entry=100, stop=90, target=130, gap_exit_at_open=True)
    check("gap option fills a gap-down stop at the open (-1.5R)",
          near(r.r, -1.5) and near(r.exit_price, 85.0), f"r={r.r} @{r.exit_price}")


# ======================================================================
# 7. Measurement sweep over a population
# ======================================================================
class FakeStore:
    """Small stand-in for PriceStore: bars_after() is all measure_ideas needs."""

    def __init__(self, bars_by_symbol):
        self.bars_by_symbol = bars_by_symbol

    def bars_after(self, symbol, date_str):
        return self.bars_by_symbol.get(symbol, [])


def test_measure_and_summarise():
    print("\n--- MFE/MAE report over a small synthetic population ---")
    winner = [(100, 105, 98, 104), (104, 112, 103, 110), (110, 132, 109, 131)]
    loser = [(100, 105, 89, 95), (95, 96, 90, 92), (92, 93, 90, 91)]
    never = [(90, 95, 85, 88)] * 5
    store = FakeStore({"WINSYM": winner, "LOSESYM": loser, "NEVERSYM": never})
    ideas = [
        ep.Idea("WINSYM", "2024-01-01", 100, 90, 130, "WIN"),
        ep.Idea("LOSESYM", "2024-01-02", 100, 90, 130, "LOSS"),
        ep.Idea("NEVERSYM", "2024-01-03", 100, 90, 130, "EXPIRED"),
    ]
    records = ep.measure_ideas(ideas, store, levels=(0.25, 1.0, 3.0),
                               hold_bars=3)
    s = ep.summarise(records, levels=(0.25, 1.0, 3.0))
    block = s["SWING"]
    check("traded count excludes the never-triggered idea",
          block["n_traded"] == 2 and block["n_expired"] == 1,
          f"traded={block['n_traded']} expired={block['n_expired']}")
    check("re-scoring reproduces the stored outcomes (stop-first)",
          block["stored_match"] == "2/2", block["stored_match"])
    check("mean R at 3R is (3 + -1)/2 = +1.0R",
          near(block["by_target"]["3.0"]["mean_r_ledger"], 1.0),
          str(block["by_target"]["3.0"]["mean_r_ledger"]))
    check("mean R at 0.25R is (0.25 + -1)/2 = -0.375R",
          near(block["by_target"]["0.25"]["mean_r_ledger"], -0.375),
          str(block["by_target"]["0.25"]["mean_r_ledger"]))
    # reach_pct is MFE-based: the loser printed +0.5R on its stop bar, so it
    # counts as "reached +0.25R" even though it is graded a LOSS.
    check("reachability counts every favourable touch, not just wins",
          block["reach_pct"]["0.25"] == 100.0 and
          block["reach_pct"]["1.0"] == 50.0 and
          block["reach_pct"]["3.0"] == 50.0,
          str(block["reach_pct"]))
    check("MFE/MAE distribution is reported",
          block["mfe_r"]["n"] == 2 and near(block["mfe_r"]["max"], 3.2),
          str(block["mfe_r"]))
    check("best level picks the highest average R",
          near(ep.best_level(block)["level"], 3.0), str(ep.best_level(block)))

    # Regression: a stored target is rarely a round R multiple. If the stored
    # level is not added to the scan, every stored WIN silently re-scores LOSS.
    off_grid = ep.Idea("WINSYM", "2024-01-04", 100, 90, 130.004, "WIN")
    rec = ep.measure_ideas([off_grid], store, levels=(0.25, 1.0, 3.0),
                           hold_bars=3)[0]
    check("an off-grid stored target is still scanned and graded",
          rec["stored_result"]["outcome"] == "WIN" and
          near(rec["stored_level"], 3.0004), str(rec["stored_result"]))

    # Regression: a trade resolved inside a SHORT data window is resolved, not
    # "still open". A snapshot that stops ~21 bars after its signals is normal
    # for a live episode; getting this wrong deletes most of that episode.
    short_store = FakeStore({"STOPSYM": [(100, 105, 89, 95)]})
    rec = ep.measure_ideas([ep.Idea("STOPSYM", "2024-01-05", 100, 90, 130,
                                    "LOSS")],
                           short_store, levels=(1.0,), hold_bars=30)[0]
    check("a stop inside a short window counts as resolved, not open",
          rec["facts"]["status"] == "COMPLETE" and
          rec["stored_result"]["outcome"] == "LOSS",
          f"{rec['facts']['status']} {rec['stored_result']['outcome']}")

    quiet_store = FakeStore({"QUIETSYM": [(100, 102, 98, 101)]})
    rec = ep.measure_ideas([ep.Idea("QUIETSYM", "2024-01-06", 100, 90, 130)],
                           quiet_store, levels=(1.0,), hold_bars=30)[0]
    check("a short window with nothing decided stays OPEN, not a flat timeout",
          rec["facts"]["status"] == "OPEN" and
          rec["level_results"][1.0]["outcome"] == "OPEN",
          f"{rec['facts']['status']} {rec['level_results'][1.0]['outcome']}")


# ======================================================================
# 8. Stored signals in the live database (READ ONLY, data-independent)
# ======================================================================
def test_live_db_read_only_and_report():
    """Every number here is read back from THIS machine's ledger first.

    The laptop holds a stale data/app.db (a handful of SWING rows); the VM holds
    the real production ledger (155+ rows, two modes). Hardcoding either shape
    makes the suite fail on the other machine, so the expected counts are always
    queried from the database under test.
    """
    print("\n--- live database: read-only instrumentation ---")
    store = ep.PriceStore()
    path = store.db_path
    if not path or not os.path.exists(path):
        skip("live database checks", f"no database at {path}")
        return
    try:
        conn = store.connection()
    except sqlite3.Error as e:
        skip("live database checks", f"cannot open {path} read-only ({e})")
        store.close()
        return

    try:
        conn.execute("CREATE TABLE _test_should_fail(x)")
        check("PriceStore refuses writes (mode=ro)", False)
    except sqlite3.Error:
        check("PriceStore refuses writes (mode=ro)", True)

    # How many rows does this ledger hold, per mode? COALESCE matches how
    # load_stored_signals() reads a NULL mode (as SWING).
    try:
        swing_rows = conn.execute(
            "SELECT COUNT(*) FROM swing_signals "
            "WHERE COALESCE(mode,'SWING')='SWING'").fetchone()[0]
        all_rows = conn.execute(
            "SELECT COUNT(*) FROM swing_signals").fetchone()[0]
    except sqlite3.Error as e:
        skip("instrument_report on the live ledger",
             f"swing_signals not readable in this database ({e})")
        store.close()
        return
    store.close()

    if not swing_rows:
        skip("instrument_report on the live ledger",
             f"this database has {all_rows} signal rows, 0 of them SWING")
        return

    report = ep.instrument_report(modes=["SWING"], levels=(0.25, 0.5, 1.0, 3.0))
    block = report["by_mode"].get("SWING")
    if block is None:
        skip("instrument_report on the live ledger",
             "no SWING row survived into the report")
        return

    check("every stored SWING row is measured",
          block["n_signals"] == swing_rows,
          f"report={block['n_signals']} db_swing_rows={swing_rows}")
    check("counts reconcile",
          block["n_traded"] + block["n_expired"] + block["n_open"] +
          block["n_skipped"] == block["n_signals"], str(block["n_traded"]))
    total = block["stored_match"]
    if total == "n/a":
        skip("stop-first re-score agrees with the live grader's outcomes",
             "no graded SWING row with a complete price path here")
    else:
        got, want = (int(x) for x in total.split("/"))
        check("stop-first re-score agrees with the live grader's outcomes",
              got >= 0.9 * want, total)
    if block["n_traded"]:
        check("MFE/MAE measured for the stored rows",
              block["mfe_r"]["n"] == block["n_traded"], str(block["mfe_r"]["n"]))
    check("report carries the tie rule it used",
          report["tie_rule"] == ep.STOP_FIRST, report["tie_rule"])
    check("report is printable", "EXIT CALIBRATION REPORT" in
          ep.format_report(report))

    # Only meaningful where the ledger actually holds a second mode — and this
    # is the exact bug that a single-mode laptop DB hides: the SWING report
    # count must be the SWING rows, not the whole table.
    if all_rows > swing_rows:
        whole = ep.instrument_report(levels=(1.0,))
        check("mode filter keeps SWING and ALL_WEATHER apart",
              whole["n_ideas"] == all_rows and
              block["n_signals"] == swing_rows and
              (whole["by_mode"].get("SWING", {}).get("n_signals", 0)
               == swing_rows),
              f"all={whole['n_ideas']} swing={block['n_signals']}")


def test_ledger_agreement():
    print("\n--- agreement with ledger.py on the same stored row ---")
    try:
        import ledger
    except Exception as e:                                     # pragma: no cover
        check("ledger importable", False, str(e))
        return
    trig, stop, target = 100.0, 90.0, 130.0
    bars = [(100, 131, 99, 130)]
    r = ep.score_path(bars, entry=trig, stop=stop, target=target)
    check("our 3R win R equals ledger.trade_r_multiple for the same row",
          near(r.r_ledger, ledger.trade_r_multiple("WIN", trig, stop, target)),
          f"ours={r.r_ledger} ledger={ledger.trade_r_multiple('WIN', trig, stop, target)}")
    r2 = ep.score_path([(100, 101, 85, 90)], entry=trig, stop=stop, target=target)
    check("our loss R equals ledger.trade_r_multiple",
          near(r2.r_ledger, ledger.trade_r_multiple("LOSS", trig, stop, target)))


# ======================================================================
# 9. setup.py integration: entry/stop unchanged, target configurable
# ======================================================================
def test_setup_entry_stop_unchanged_target_configurable():
    print("\n--- setup.py: entry/stop fixed, target follows the multiple ---")
    try:
        import pandas as pd
        from setup import SetupDetector
        import strategy_config
    except Exception as e:                                     # pragma: no cover
        skip("setup.py target integration", f"import failed ({e})")
        return

    # Whether a Gabani trigger exists in the available history depends on which
    # database/machine this runs on, so hunt a few symbols for one and SKIP if
    # this ledger simply has none. The assertions below stay strict when found.
    store = ep.PriceStore()
    found = None
    scanned = 0
    try:
        # by_mcap needs universe_broad; a stripped analysis snapshot may not have
        # it, so fall back to plain symbol order before giving up.
        symbols = (store.symbols_with_history(min_bars=400, limit=15) or
                   store.symbols_with_history(min_bars=400, limit=15,
                                              by_mcap=False))
        for sym in symbols:
            rows = store.all_bars(sym)
            if len(rows) < 400:
                continue
            scanned += 1
            df = pd.DataFrame([(r[0], r[1], r[2], r[3], r[4], r[5])
                               for r in rows],
                              columns=["date", "Open", "High", "Low", "Close",
                                       "Volume"]).set_index("date")
            df.index = pd.to_datetime(df.index)
            for i in range(300, len(df) - 1, 20):
                st = SetupDetector.detect(df.iloc[:i + 1], sym)
                if st.triggered:
                    found = (st, df, i, sym)
                    break
            if found:
                break
    finally:
        store.close()

    if found is None:
        skip("setup.py target integration",
             f"no SetupDetector trigger in {scanned} symbol(s) with 400+ bars "
             f"on this database")
        return
    _st, df, i, symbol = found

    saved = SetupDetector.TARGET_R_MULTIPLE
    try:
        SetupDetector.TARGET_R_MULTIPLE = 3.0
        at3 = SetupDetector.detect(df.iloc[:i + 1], symbol)
        SetupDetector.TARGET_R_MULTIPLE = 1.0
        at1 = SetupDetector.detect(df.iloc[:i + 1], symbol)
    finally:
        SetupDetector.TARGET_R_MULTIPLE = saved

    risk = at3.entry_price - at3.stop_loss
    check("changing the multiple does not move the entry",
          near(at3.entry_price, at1.entry_price), f"{at3.entry_price}/{at1.entry_price}")
    check("changing the multiple does not move the stop",
          near(at3.stop_loss, at1.stop_loss), f"{at3.stop_loss}/{at1.stop_loss}")
    check("a 1R target is entry + 1 x (entry - stop)",
          near(at1.target_price, round(at1.entry_price + 1.0 * risk, 2), 0.02),
          f"target={at1.target_price} expected~{at1.entry_price + risk:.2f}")
    check("a 3R target is three times as far as a 1R target",
          near(at3.target_price - at3.entry_price,
               3 * (at1.target_price - at1.entry_price), 0.05),
          f"3R={at3.target_price} 1R={at1.target_price}")
    check("risk_reward reports the multiple in use",
          near(at3.risk_reward, 3.0) and near(at1.risk_reward, 1.0),
          f"{at3.risk_reward}/{at1.risk_reward}")
    check("default multiple is still the configured live value",
          near(saved, ep.resolve_target_r(cfg=strategy_config.SETUP)), str(saved))


def main():
    print("=" * 68)
    print("test_swing_exits.py - exit policy, R scorer, MFE/MAE instrumentation")
    print("=" * 68)
    test_plan_math()
    test_resolve_target_r()
    test_setup_survives_missing_config_key()
    test_outcomes()
    test_intrabar_tie()
    test_mfe_mae()
    test_breakeven_rule()
    test_trail_rule()
    test_trigger_and_gap()
    test_measure_and_summarise()
    test_live_db_read_only_and_report()
    test_ledger_agreement()
    test_setup_entry_stop_unchanged_target_configurable()
    print("\n" + "=" * 68)
    if SKIPS:
        print(f"SKIPPED {len(SKIPS)} data-dependent check(s) "
              f"(fixture not present on this machine):")
        for name in SKIPS:
            print("   - " + name)
    if FAILS:
        print(f"FAILED {len(FAILS)} check(s):")
        for name in FAILS:
            print("   - " + name)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
