"""Background EOD scheduler — starts with the FastAPI service."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

IST = pytz.timezone("Asia/Kolkata")
_scheduler = None

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
        print("[SCHEDULER] swing scan complete")
    except Exception as e:
        print(f"[SCHEDULER] swing scan failed: {e}")

def start():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=IST)
    _scheduler.add_job(_daily_job,
        CronTrigger(hour=15, minute=45, timezone=IST),
        id="daily_update", replace_existing=True)
    _scheduler.add_job(_swing_job,
        CronTrigger(hour=16, minute=15, timezone=IST),
        id="swing_scan", replace_existing=True)
    _scheduler.start()
    print("[SCHEDULER] started — daily@15:45 IST, swing@16:15 IST")

def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None