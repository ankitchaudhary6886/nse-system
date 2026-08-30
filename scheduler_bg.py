"""Background scheduler — data quality + EOD + swing scan + weekly retrain."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

IST = pytz.timezone("Asia/Kolkata")
_scheduler = None


def _data_quality_job():
    print("[SCHEDULER] data quality started")
    try:
        import data_quality
        data_quality.run(send_alert=True)
        print("[SCHEDULER] data quality complete")
    except Exception as e:
        print(f"[SCHEDULER] data quality failed: {e}")


def _daily_job():
    print("[SCHEDULER] daily update started")
    try:
        import daily_update
        daily_update.run()
        print("[SCHEDULER] daily update complete")
    except Exception as e:
        print(f"[SCHEDULER] daily update failed: {e}")


def _swing_job():
    print("[SCHEDULER] swing scan started")
    try:
        import swing_live
        swing_live.update_outcomes()
        swing_live.scan()
        _drift_check()
        print("[SCHEDULER] swing scan complete")
    except Exception as e:
        print(f"[SCHEDULER] swing scan failed: {e}")


def _drift_check():
    """Warn if recent live win-rate decays."""
    try:
        import db
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT outcome FROM swing_signals "
            "WHERE outcome IN ('WIN','LOSS') "
            "ORDER BY signal_date DESC LIMIT 40"
        ).fetchall()
        conn.close()

        if len(rows) < 15:
            print("[DRIFT] not enough graded trades yet")
            return

        wins = sum(1 for r in rows if r[0] == "WIN")
        live_wr = wins / len(rows)

        if live_wr < 0.35:
            msg = (f"[DRIFT] ⚠️ live win-rate {live_wr:.0%} over last "
                   f"{len(rows)} graded — review setup quality")
            print(msg)
            try:
                import swing_alerts
                swing_alerts.send(msg)
            except Exception:
                pass
        else:
            print(f"[DRIFT] ok — live win-rate {live_wr:.0%} "
                  f"({len(rows)} graded)")
    except Exception as e:
        print(f"[DRIFT] check skipped: {e}")


def _retrain_job():
    print("[SCHEDULER] weekly meta retrain started")
    try:
        import meta_model
        meta_model.train()
        meta_model._MODEL = None
        print("[SCHEDULER] weekly meta retrain complete")
    except Exception as e:
        print(f"[SCHEDULER] retrain failed: {e}")


def start():
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone=IST)

    _scheduler.add_job(
        _data_quality_job,
        CronTrigger(hour=15, minute=30, timezone=IST),
        id="data_quality",
        replace_existing=True,
    )

    _scheduler.add_job(
        _daily_job,
        CronTrigger(hour=15, minute=45, timezone=IST),
        id="daily_update",
        replace_existing=True,
    )

    _scheduler.add_job(
        _swing_job,
        CronTrigger(hour=16, minute=15, timezone=IST),
        id="swing_scan",
        replace_existing=True,
    )

    _scheduler.add_job(
        _retrain_job,
        CronTrigger(day_of_week="sat", hour=9, minute=0, timezone=IST),
        id="meta_retrain",
        replace_existing=True,
    )

    _scheduler.start()
    print("[SCHEDULER] started — dq@15:30, daily@15:45, "
          "swing@16:15, retrain@Sat 09:00 IST")


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None