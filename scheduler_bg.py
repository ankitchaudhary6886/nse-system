"""Background scheduler — dq + daily + delivery + swing (+veto purge) +
macro + patterns + templates + weekly/monthly jobs. No intraday layers."""
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


def _purge_vetoed():
    """Remove today's signals for fundamentally vetoed symbols."""
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
        import fundamentals_refresh
        fundamentals_refresh.auto()
        log.info("weekly fundamentals refresh complete")
    except Exception as e:
        log.exception(f"fundamentals refresh failed: {e}")


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
                import swing_alerts
                swing_alerts.send(msg)
            except Exception:
                pass
        else:
            log.info(f"[DRIFT] ok — live win-rate {live_wr:.0%} "
                     f"({len(rows)} graded)")
    except Exception as e:
        log.warning(f"[DRIFT] check skipped: {e}")


def start():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=IST)
    _scheduler.add_job(_data_quality_job,
                       CronTrigger(hour=15, minute=30, timezone=IST),
                       id="data_quality", replace_existing=True)
    _scheduler.add_job(_daily_job,
                       CronTrigger(hour=15, minute=45, timezone=IST),
                       id="daily_update", replace_existing=True)
    _scheduler.add_job(_delivery_job,
                       CronTrigger(hour=16, minute=0, timezone=IST),
                       id="delivery_fetch", replace_existing=True)
    _scheduler.add_job(_swing_job,
                       CronTrigger(hour=16, minute=15, timezone=IST),
                       id="swing_scan", replace_existing=True)
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
    _scheduler.add_job(_fundamentals_job,
                       CronTrigger(day_of_week="sat", hour=8, minute=0,
                                   timezone=IST),
                       id="fundamentals_refresh", replace_existing=True)
    _scheduler.add_job(_retrain_job,
                       CronTrigger(day_of_week="sat", hour=9, minute=0,
                                   timezone=IST),
                       id="meta_retrain", replace_existing=True)
    _scheduler.add_job(_validate_mc_job,
                       CronTrigger(day_of_week="mon", hour=8, minute=0,
                                   timezone=IST),
                       id="validate_mc", replace_existing=True)
    _scheduler.add_job(_value_radar_job,
                       CronTrigger(day_of_week="sun", hour=9, minute=0,
                                   timezone=IST),
                       id="value_radar", replace_existing=True)
    _scheduler.add_job(_validate_wf_job,
                       CronTrigger(day=1, hour=10, minute=0,
                                   timezone=IST),
                       id="validate_wf", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started — dq@15:30, daily@15:45, delivery@16:00, "
             "swing@16:15(+veto purge), inst@16:45, macro@17:30, "
             "patterns@18:05, templates@18:35, fund@Sat08:00, "
             "retrain@Sat09:00, mc@Mon08:00, wf@1st10:00 IST")


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler stopped")