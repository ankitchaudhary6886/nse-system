import sys
import ingest_prices
import technicals
import scan
import ml_predict
import events
import telegram_alerts
import sheets_sync
import swing_live

def run():
    print("1/8 incremental prices...")
    ingest_prices.run(show_every=0)
    print("2/8 technicals...")
    technicals.compute_all()
    print("3/8 fundamental scan...")
    scan.run()
    print("4/8 ML predictions...")
    ml_predict.predict_all()
    print("5/8 events...")
    events.detect()
    print("6/8 swing desk...")
    try:
        swing_live.update_outcomes()
        swing_live.scan()
    except Exception as e:
        print("swing scan skipped:", e)
    print("7/8 telegram...")
    telegram_alerts.report()
    print("8/8 google sheets...")
    sheets_sync.sync()
    print("DAILY UPDATE COMPLETE ✔")

if len(sys.argv) > 1 and sys.argv[1] == "run":
    run()