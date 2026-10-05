---
name: nse-terminal-pipeline-ops
description: Use when running, scheduling, diagnosing, or debugging the NSE terminal's EOD pipeline and cron jobs — covers the exact stage order, IST-vs-UTC log times, gate ordering, per-job commands, and what "empty result" actually means.
---

# NSE Terminal — Pipeline & Job Operations

## 1. The EOD chain and its real order

`daily_update.py:run()` — 10 stages, each isolated in `_safe()` so one failure
never stops the rest. Source of truth: `.agents/cache/jobs_index.json`.

| # | Stage | Module → entry | Writes |
|---|---|---|---|
| 1 | prices | `ingest_prices.run(show_every=0)` | `prices_daily`, `price_meta` |
| 2 | technicals | `technicals.compute_all()` | `technicals_daily` |
| 3 | scan | `scan.run()` | `scan_results`, `scan_reasons`, `pipeline` |
| 4 | ml | `ml_predict.predict_all()` | `ml_predictions` |
| 5 | pwin | `pwin_cache.refresh_all()` | `pwin_daily` |
| 6 | toppicks | `top_picks.compute(force=True)` | `top_picks` |
| 7 | events | `events.detect()` | `events` |
| 8 | swing | `swing_live.update_outcomes()` + `swing_live.scan()` | `swing_signals` |
| 9 | telegram | `telegram_alerts.report()` | — |
| 10 | sheets | `sheets_sync.sync()` | Google Sheets |

**Known ordering defect (F-09):** `scan` (3) reads `ml_predictions` but
`ml_predict` (4) writes it. Today's ML score can never influence today's scan.
Do not "fix" this by reordering alone — `ml_predictions` is empty anyway (F-03),
so the swap must come with a retrain.

Everything **not** in `daily_update` is its own APScheduler job: patterns 18:05,
templates 18:35, trend 15:50, delivery 16:00, research warm 16:20, institutional
16:45, macro 17:30, league Mon-Fri 19:00, and the weekend/monthly jobs.

## 2. Time discipline (the #1 triage mistake)

- Scheduler cron triggers are **IST** (`Asia/Kolkata`).
- `journalctl` and `log_utils` file timestamps are **UTC**.
- `IST = UTC + 5:30`. A job at 16:15 IST appears in the journal at **10:45 UTC**.

When asked "why didn't the 16:15 job run?", first convert to UTC before reading
logs. An empty 16:15 IST window read at 16:20 IST is 10:50 UTC — it has not run yet.

## 3. Per-job commands (VM, after `source venv/bin/activate`)

```bash
python data_quality.py                 # 6 checks, Telegram on failure
python daily_update.py run             # the 10-stage chain
python technicals.py                   # compute_all
python scan.py                         # rule/ML blend -> scan_results
python ml_train.py                     # writes data/ml_models.pkl (v0.2-pit-safe)
python ml_predict.py                   # writes ml_predictions
python meta_model.py train             # writes data/meta_model.pkl (v8-pit-safe)
python meta_model.py SYMBOL            # SHAP "why" for one symbol
python pwin_cache.py                   # P(WIN) -> pwin_daily
python top_picks.py                    # composite -> top_picks
python swing_live.py                   # signal scan
python swing_live.py backfill          # historical outcome grading
python institutional.py                # accumulation footprint
python delivery.py fetch               # NSE bhavcopy delivery %
python delivery.py backfill 30
python macro.py                        # FII/DII fetch (usually blocked on VM)
python macro.py set 1234 -567          # manual FII/DII override
python patterns.py run                 # pattern tags + grader gate
python template_match.py run           # DTW similarity
python breadth.py                      # % above 50-EMA
python sector_gate.py                  # sector RS top-3
python validate.py all                 # Monte Carlo + walk-forward
python model_report.py lift            # C3 lift history
python trader_league.py selftest       # must print 28/28
tail -20 data/logs/scheduler.log
```

## 4. The live gate order — do not reorder

`swing_live.scan()` applies, in this exact sequence:

1. `regime.MarketRegime.compute()` — raises if no benchmark
2. regime allows normal swing? if not → all-weather path (its own breadth gate ≥ 0.35)
3. `breadth.breadth_ok()` — `above50 ≥ 0.50` **and** `adv ≥ dec`
4. `sector_gate` — sector in the **top-3** by `0.6·perf1m + 0.4·perf3m`
5. ≥ 280 price bars
6. `scanner.Screener.evaluate().passed`
7. `setup.SetupDetector.detect().triggered`
8. **staleness guard** — `signal_date == last bar date` (`MAX_SHIFT = 2`)
9. `fund_veto.vetoed()` — `debt_eq > 3` OR `roce < 8` OR `promoter < 20`
10. INSERT `swing_signals` (PENDING)
11. `alerts.notify_setup()` — re-runs the veto (F-13)

`top_picks` runs: pwin → (if empty, refresh) → delete today → maps → veto →
composite → sort → setup detect on top-50 only → +0.10 live-setup bonus.
`patterns` runs: gate filter → detect (confidence ≥ 58) → veto **only if
BULLISH** → write tags → `grade_all()` + `report()`.

## 5. Diagnosing "the pipeline produced nothing"

Work down this list — most empty results are one of these, not a code bug.

| Symptom | Likely cause | Check |
|---|---|---|
| `top_picks` empty | F-02 — meta model refused → `pwin_daily` empty | `SELECT COUNT(*) FROM pwin_daily` |
| `scan_results.passed` all 0 | F-03 — `ml_models.pkl` version mismatch → `ml_predictions` empty | `SELECT COUNT(*), MAX(prediction_date) FROM ml_predictions` |
| `swing_signals` empty | regime DEFENSIVE, or `breadth_daily` empty (F-01 staleness), or veto | `python regime.py`, `python breadth.py` |
| `pattern_grades` = 0 | patterns job never ran on fresh data (F-04) | `SELECT COUNT(*) FROM pattern_tags` |
| `delivery_daily` / `macro_flow` empty on VM | **expected** — NSE blocks datacenter IPs | the fetch error in the journal |
| Everything empty on laptop | local DB is ~40 days stale (F-01) | check the VM instead |
| Job never fired | it is a weekend/monthly job, or read in the wrong timezone | `jobs_index.json` |

Never report an empty table as "no setups today" without checking which upstream
table is empty. An absent value is not a zero.

## 6. Adding a job

```python
def _my_job():
    log.info("my job started")
    try:
        import my_module
        my_module.run()
        log.info("my job complete")
    except Exception as e:
        log.exception(f"my job failed: {e}")
```
Then `_scheduler.add_job(_my_job, CronTrigger(hour=H, minute=M, timezone=IST),
id="my_job", replace_existing=True)` and update the banner string in `start()`.
Log via `log_utils.get_logger("scheduler")`. Never let an exception escape — the
scheduler thread dies silently.

## 7. Data-quality thresholds (for triage)

`data_quality.py`: CRITICAL staleness **≥5 days**, WARN **≥3**; suspicious jump
**≥35 %**; missing-recent-symbol coverage **>25 % CRITICAL**, **>10 % WARN**;
OHLC invalid if `close > high*1.02` or `close < low*0.98`.
Note F-11: the script **deletes** `data_quality_log` before every run, so only
the latest run survives.

## 8. Rules

- **A zero exit code is not a result.** Read the table the job claims to write.
- **A DB-only change needs no restart**; a `.py` change does.
- Keep every optional integration in `try/except` — the UI must never blank.
- Never run the 15:30-19:00 IST chain manually on the VM at the same time as
  the scheduler; there is no lock shared with the API.
- Heavy jobs (replay, pool rebuild, retrain) belong on the VM, never on the
  laptop while editing, and not concurrently (Oracle free tier).
