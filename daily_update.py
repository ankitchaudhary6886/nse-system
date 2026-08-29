import sys
import ingest_prices
import technicals
import scan
import ml_predict
import events
import swing_live

def _safe(name, fn):
    print(f"... {name}")
    try:
        fn()
        print(f"ok {name}")
    except Exception as e:
        print(f"skip {name}: {e}")

def _telegram():
    import telegram_alerts
    telegram_alerts.report()

def _sheets():
    import sheets_sync
    sheets_sync.sync()

def run():
    _safe("prices", lambda: ingest_prices.run(show_every=0))
    _safe("technicals", technicals.compute_all)
    _safe("scan", scan.run)
    _safe("ml", ml_predict.predict_all)
    _safe("events", events.detect)
    _safe("swing", lambda: (swing_live.update_outcomes(), swing_live.scan()))
    _safe("telegram", _telegram)
    _safe("sheets", _sheets)
    print("DAILY UPDATE COMPLETE")

if len(sys.argv) > 1 and sys.argv[1] == "run":
    run()