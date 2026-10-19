"""Background scheduler — daily chain + swing + research cache + pool
rebuild + patterns + fundamentals + value radar + positional + trend +
validation."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from log_utils import get_logger

IST = pytz.timezone("Asia/Kolkata")
log = get_logger("scheduler")

_scheduler = None


def _data_quality_job():
    log.info("data quality started")
    try:
        import data_quality
        data_quality.run(send_alert=True)
        log.info("data quality complete")
    except Exception as e:
        log.exception(f"data quality failed: {e}")


def _daily_job():
    log.info("daily update started")
    try:
        import daily_update
        daily_update.run()
        log.info("daily update complete")
    except Exception as e:
        log.exception(f"daily update failed: {e}")


def _trend_job():
    log.info("trend scanner started")
    try:
        import trend_scanner
        trend_scanner.compute()
        log.info("trend scanner complete")
    except Exception as e:
        log.exception(f"trend scanner failed: {e}")


def _swing_job():
    log.info("swing scan started")
    try:
        import swing_live
        swing_live.update_outcomes()
        swing_live.scan()
        _purge_vetoed()
        _drift_check()
        log.info("swing scan complete")
    except Exception as e:
        log.exception(f"swing scan failed: {e}")


def _warm_research_job():
    log.info("research cache warm started")
    try:
        import research_cockpit
        n = research_cockpit.warm_cache(max_symbols=200)
        log.info(f"research cache warm complete: {n} computed")
    except Exception as e:
        log.exception(f"research cache warm failed: {e}")


def _pool_rebuild_job():
    """Weekly full rebuild of setup_pool — the corpus that powers
    signature matching in the research cockpit. 800 symbols × 5y × step 5.
    ~8-10 minutes."""
    log.info("setup pool rebuild started")
    try:
        import build_setup_pool
        n = build_setup_pool.build(limit=800, step=5, clear=True)
        # Refresh count after rebuild
        try:
            build_setup_pool.stats()
        except Exception:
            pass
        log.info(f"setup pool rebuild complete: {n} setups added")
    except Exception as e:
        log.exception(f"setup pool rebuild failed: {e}")


def _purge_vetoed():
    try:
        import db
        import fund_veto
        import datetime as dt
        conn = db.get_conn()
        today = dt.date.today().isoformat()
        rows = conn.execute(
            "SELECT symbol FROM swing_signals WHERE signal_date=?",
            (today,)).fetchall()
        killed = []
        for (sym,) in rows:
            bad, why = fund_veto.vetoed(sym, conn=conn)
            if bad:
                conn.execute(
                    "DELETE FROM swing_signals "
                    "WHERE signal_date=? AND symbol=?",
                    (today, sym))
                killed.append(f"{sym} ({why})")
        conn.commit()
        conn.close()
        if killed:
            log.info(f"[VETO] purged {len(killed)} of today's signals: "
                     f"{', '.join(killed)}")
    except Exception as e:
        log.warning(f"[VETO] purge skipped: {e}")


def _institutional_job():
    log.info("institutional refresh started")
    try:
        import institutional
        institutional.refresh()
        log.info("institutional refresh complete")
    except Exception as e:
        log.exception(f"institutional refresh failed: {e}")


def _macro_job():
    log.info("macro FII/DII fetch started")
    try:
        import macro
        macro.refresh()
        log.info("macro fetch complete")
    except Exception as e:
        log.exception(f"macro fetch failed: {e}")


def _delivery_job():
    log.info("delivery fetch started")
    try:
        import delivery
        delivery.fetch()
        log.info("delivery fetch complete")
    except Exception as e:
        log.exception(f"delivery fetch failed: {e}")


def _pattern_job():
    log.info("pattern scan started")
    try:
        import patterns
        patterns.run()
        log.info("pattern scan complete")
    except Exception as e:
        log.exception(f"pattern scan failed: {e}")


def _template_job():
    log.info("DTW template scan started")
    try:
        import template_match
        template_match.run()
        log.info("DTW template scan complete")
    except Exception as e:
        log.exception(f"DTW template scan failed: {e}")


def _fundamentals_job():
    log.info("weekly fundamentals refresh started")
    try:
        import fundamentals_tv
        fundamentals_tv.run()
        log.info("weekly fundamentals refresh complete")
    except Exception as e:
        log.exception(f"fundamentals refresh failed: {e}")
    # After any fundamentals refresh, re-derive the algebraically implied fields
    # and (only when a new snapshot exists) fill the veto-only ownership fields.
    try:
        import db
        import fundamentals_derive
        derived = fundamentals_derive.run(apply=True)
        log.info(f"fundamentals derive: {derived.get('applied')} rows")
    except Exception as e:
        log.exception(f"fundamentals derive failed: {e}")
    try:
        import db
        import fundamentals_enrich
        conn = db.get_conn()
        try:
            enriched = fundamentals_enrich.enrich(conn=conn, dry_run=False)
        finally:
            conn.close()
        log.info(f"fundamentals enrich: touched {enriched.get('rows_touched')} "
                 f"rows (PIT-invalid snapshot, live veto only)")
    except Exception as e:
        log.exception(f"fundamentals enrich failed: {e}")


def _token_job():
    """Keep the Fyers token alive without a browser (or nag once a day).

    The pin-based refresh-token flow can renew the access token automatically
    as long as FYERS_PIN is configured and a refresh token exists. If it cannot,
    one Telegram message tells the owner that a manual login is due — never a
    silent data gap.
    """
    try:
        import fyers_client
        client = fyers_client.FyersClient()
        if client.token and not client.token_store.expired():
            return
        result = client.refresh_access_token()
        log.info(f"[FYERS] access token auto-renewed until "
                 f"{result.get('expires_at')}")
    except Exception as e:
        log.warning(f"[FYERS] automatic token renewal unavailable: {e}")
        try:
            import swing_alerts
            swing_alerts.send(
                "Fyers login due: automatic token renewal failed. Open the "
                "terminal, press the '⚡ Data' button and follow 'Open Fyers "
                "login' (2 minutes). Free price sources keep working until then.")
        except Exception as notify_exc:
            log.warning(f"[FYERS] login reminder not sent: {notify_exc}")


def _official_eod_job():
    """FREE official NSE end-of-day ingestion (no login, no key).

    NSE archive files (sec_bhavdata_full + ind_close_all) are the raw official
    source: prices, volume, delivery% and every index close. They publish in the
    evening, so this runs after the Yahoo-based 15:45 chain and corrects it with
    the exchange's own files.
    """
    log.info("official NSE EOD ingestion started")
    try:
        import db
        import nse_eod_ingest
        conn = db.get_conn()
        try:
            result = nse_eod_ingest.catch_up(conn, days_back=7)
        finally:
            conn.close()
        log.info(f"official NSE EOD complete: attempted={result.get('attempted')} "
                 f"ok={result.get('ok')} holidays={len(result.get('holidays') or [])} "
                 f"errors={len(result.get('errors') or [])}")
        # Optional Fyers gap-fill for holes the official files could not cover.
        try:
            import backfill_gaps
            conn = db.get_conn()
            try:
                gaps = backfill_gaps.fill_with_fyers(conn, days=7,
                                                     progress=False)
            finally:
                conn.close()
            log.info(f"fyers gap-fill: {gaps}")
        except Exception as exc:
            log.warning(f"fyers gap-fill skipped: {exc}")
    except Exception as e:
        log.exception(f"official NSE EOD failed: {e}")


def _official_retry_job():
    """Morning retry/catch-up in case the evening archive fetch was delayed."""
    try:
        import db
        import nse_eod_ingest
        conn = db.get_conn()
        try:
            result = nse_eod_ingest.catch_up(conn, days_back=7)
        finally:
            conn.close()
        log.info(f"official NSE EOD morning retry: ok={result.get('ok')} "
                 f"attempted={result.get('attempted')}")
    except Exception as e:
        log.warning(f"official NSE EOD morning retry failed: {e}")


def _governance_job():
    """Weekly free governance feed: exchange announcements + shareholding pledge.

    Both sources are free but may be blocked from cloud IPs; every step is
    independently guarded so one block does not lose the rest. Announcements
    are DATED (announced_at is public time, so replay-safe); pledge rows carry
    the filing period end.
    """
    log.info("weekly governance feed started")
    try:
        import datetime as _dt
        import announcements
        end = _dt.date.today()
        start = end - _dt.timedelta(days=30)
        items = announcements.fetch_nse(start.isoformat(), end.isoformat())
        conn = db.get_conn()
        try:
            announcements.ensure_tables(conn)
            stored = announcements.store(conn, items)
        finally:
            conn.close()
        log.info(f"[GOV] announcements stored: {stored}")
    except Exception as e:
        log.warning(f"[GOV] announcements unavailable (NSE blocks cloud IPs): {e}")
    try:
        import pledge_ingest
        import universe_helper as U
        conn = db.get_conn()
        try:
            pledge_ingest.ensure_tables(conn)
            symbols = U.band_universe(conn, 200)
            rows = []
            # XBRL first: it is the only free source that actually states the
            # promoter pledge percentage (the JSON master has no pledge field).
            try:
                rows += pledge_ingest.fetch_nse_pledge_xbrl(symbols)
            except Exception as e:
                log.warning(f"[GOV] pledge XBRL unavailable: {e}")
            try:
                rows += pledge_ingest.fetch_nse_shareholding(symbols)
            except Exception as e:
                log.warning(f"[GOV] shareholding JSON unavailable: {e}")
            if rows:
                # The module exposes no public store; _store is its row writer.
                pledge_ingest._store(conn, rows)
            applied = pledge_ingest.apply_to_fundamentals(conn, dry_run=False)
        finally:
            conn.close()
        log.info(f"[GOV] pledge rows fetched={len(rows)} applied={applied}")
    except Exception as e:
        log.warning(f"[GOV] pledge feed unavailable (CSV fallback remains): {e}")


def _retrain_job():
    log.info("weekly meta retrain started")
    try:
        import meta_model
        meta_model.train()
        meta_model._MODEL = None
        log.info("weekly meta retrain complete")
    except Exception as e:
        log.exception(f"retrain failed: {e}")


def _value_radar_job():
    log.info("value radar started")
    try:
        import value_radar
        value_radar.report()
        log.info("value radar complete")
    except Exception as e:
        log.exception(f"value radar failed: {e}")


def _positional_job():
    log.info("positional scan started")
    try:
        import positional_scanner
        positional_scanner.compute()
        positional_scanner.report()
        log.info("positional scan complete")
    except Exception as e:
        log.exception(f"positional scan failed: {e}")


def _validate_mc_job():
    log.info("weekly monte-carlo started")
    try:
        import validate
        validate.run_mode("mc")
        log.info("monte-carlo complete")
    except Exception as e:
        log.exception(f"monte-carlo failed: {e}")


def _validate_wf_job():
    log.info("monthly walk-forward started")
    try:
        import validate
        validate.run_mode("wf")
        log.info("walk-forward complete")
    except Exception as e:
        log.exception(f"walk-forward failed: {e}")


def _drift_check():
    try:
        import db
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT outcome FROM swing_signals "
            "WHERE outcome IN ('WIN','LOSS') "
            "ORDER BY signal_date DESC LIMIT 40").fetchall()
        conn.close()
        if len(rows) < 15:
            log.info("[DRIFT] not enough graded trades yet")
            return
        wins = sum(1 for r in rows if r[0] == "WIN")
        live_wr = wins / len(rows)
        if live_wr < 0.35:
            msg = (f"[DRIFT] ⚠️ live win-rate {live_wr:.0%} over last "
                   f"{len(rows)} graded — review setup quality")
            log.warning(msg)
            try:
                from alerts import send
                send(msg)
            except Exception:
                pass
        else:
            log.info(f"[DRIFT] ok — live win-rate {live_wr:.0%} "
                     f"({len(rows)} graded)")
    except Exception as e:
        log.warning(f"[DRIFT] check skipped: {e}")


def _league_job():
    """Trader League (#087): store today's signals from the 14 books +
    our Swing Desk, then re-simulate the live Rs 10 lakh paper league."""
    log.info("trader league started")
    try:
        import trader_league
        rep = trader_league.run_live()
        log.info(f"trader league complete: {rep}")
    except Exception as e:
        log.exception(f"trader league failed: {e}")


def _league_scorecard_job():
    """Weekly Telegram scorecard of the league."""
    try:
        import trader_league
        ok = trader_league.send_scorecard()
        log.info(f"league scorecard sent={ok}")
    except Exception as e:
        log.exception(f"league scorecard failed: {e}")


def _when(trigger):
    """Render a cron trigger as a short IST string, e.g. 'mon-fri 19:30'.

    Derived from the trigger APScheduler actually holds rather than a
    hand-written schedule, so the startup banner cannot drift from the
    add_job calls above.
    """
    fields = getattr(trigger, "fields", None)
    if not fields:
        return "once"
    f = {fl.name: str(fl) for fl in fields}
    clock = f"{f.get('hour', '*')}:{f.get('minute', '*')}"
    if f.get("day_of_week", "*") != "*":
        return f"{f['day_of_week']} {clock}"
    if f.get("day", "*") != "*":
        return f"day {f['day']} {clock}"
    return clock


def start():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=IST)
    # ---- Weekday chain ----
    _scheduler.add_job(_data_quality_job,
                       CronTrigger(hour=15, minute=30, timezone=IST),
                       id="data_quality", replace_existing=True)
    _scheduler.add_job(_daily_job,
                       CronTrigger(hour=15, minute=45, timezone=IST),
                       id="daily_update", replace_existing=True)
    _scheduler.add_job(_trend_job,
                       CronTrigger(hour=15, minute=50, timezone=IST),
                       id="trend_scan", replace_existing=True)
    _scheduler.add_job(_delivery_job,
                       CronTrigger(hour=16, minute=0, timezone=IST),
                       id="delivery_fetch", replace_existing=True)
    _scheduler.add_job(_swing_job,
                       CronTrigger(hour=16, minute=15, timezone=IST),
                       id="swing_scan", replace_existing=True)
    _scheduler.add_job(_warm_research_job,
                       CronTrigger(hour=16, minute=20, timezone=IST),
                       id="research_warm", replace_existing=True)
    _scheduler.add_job(_institutional_job,
                       CronTrigger(hour=16, minute=45, timezone=IST),
                       id="institutional", replace_existing=True)
    _scheduler.add_job(_macro_job,
                       CronTrigger(hour=17, minute=30, timezone=IST),
                       id="macro_flow", replace_existing=True)
    _scheduler.add_job(_pattern_job,
                       CronTrigger(hour=18, minute=5, timezone=IST),
                       id="pattern_scan", replace_existing=True)
    _scheduler.add_job(_template_job,
                       CronTrigger(hour=18, minute=35, timezone=IST),
                       id="template_scan", replace_existing=True)
    # Official raw NSE archives (free, no login): evening pull + morning retry.
    _scheduler.add_job(_official_eod_job,
                       CronTrigger(day_of_week="mon-fri", hour=19, minute=30,
                                   timezone=IST),
                       id="official_eod", replace_existing=True)
    _scheduler.add_job(_official_retry_job,
                       CronTrigger(hour=8, minute=15, timezone=IST),
                       id="official_eod_retry", replace_existing=True)
    _scheduler.add_job(_league_job,
                       CronTrigger(day_of_week="mon-fri", hour=19,
                                   minute=0, timezone=IST),
                       id="trader_league", replace_existing=True)
    # ---- Weekend jobs ----
    _scheduler.add_job(_pool_rebuild_job,
                       CronTrigger(day_of_week="sun", hour=6, minute=0,
                                   timezone=IST),
                       id="pool_rebuild", replace_existing=True)
    _scheduler.add_job(_fundamentals_job,
                       CronTrigger(day_of_week="sat", hour=8, minute=0,
                                   timezone=IST),
                       id="fundamentals_refresh", replace_existing=True)
    # Free governance feed (vendor-free): NSE corporate announcements + dated
    # shareholding/pledge. Runs after the fundamentals refresh so the merged
    # ownership/pledge values are present for the week's veto checks.
    _scheduler.add_job(_governance_job,
                       CronTrigger(day_of_week="sat", hour=8, minute=30,
                                   timezone=IST),
                       id="governance_feed", replace_existing=True)
    # Every morning before the market: renew the broker token from the stored
    # refresh token (needs FYERS_PIN), or remind the owner once.
    _scheduler.add_job(_token_job,
                       CronTrigger(hour=8, minute=10, timezone=IST),
                       id="fyers_token", replace_existing=True)
    _scheduler.add_job(_retrain_job,
                       CronTrigger(day_of_week="sat", hour=9, minute=0,
                                   timezone=IST),
                       id="meta_retrain", replace_existing=True)
    _scheduler.add_job(_positional_job,
                       CronTrigger(day_of_week="sat", hour=10, minute=0,
                                   timezone=IST),
                       id="positional_scan", replace_existing=True)
    _scheduler.add_job(_value_radar_job,
                       CronTrigger(day_of_week="sun", hour=9, minute=0,
                                   timezone=IST),
                       id="value_radar", replace_existing=True)
    _scheduler.add_job(_league_scorecard_job,
                       CronTrigger(day_of_week="sat", hour=11, minute=0,
                                   timezone=IST),
                       id="league_scorecard", replace_existing=True)
    # ---- Monthly ----
    _scheduler.add_job(_validate_mc_job,
                       CronTrigger(day_of_week="mon", hour=8, minute=0,
                                   timezone=IST),
                       id="validate_mc", replace_existing=True)
    _scheduler.add_job(_validate_wf_job,
                       CronTrigger(day=1, hour=10, minute=0,
                                   timezone=IST),
                       id="validate_wf", replace_existing=True)
    _scheduler.start()
    registered = sorted(_scheduler.get_jobs(), key=lambda j: j.id)
    banner = ", ".join(f"{j.id}@{_when(j.trigger)}" for j in registered)
    log.info(f"scheduler started — {len(registered)} jobs IST: {banner}")


def status():
    """Small read-only scheduler status for the UI / data-health banner."""
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        nxt = getattr(job, "next_run_time", None)
        jobs.append({"id": job.id,
                     "next_run": nxt.isoformat() if nxt else None})
    jobs.sort(key=lambda item: item["next_run"] or "")
    return {"running": bool(_scheduler.running), "jobs": jobs}


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler stopped")