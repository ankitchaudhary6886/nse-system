import sys
from log_utils import get_logger

log = get_logger("daily_update")


def _safe(name, fn):
    log.info(f"START {name}")
    try:
        fn()
        log.info(f"OK    {name}")
        return True
    except Exception as e:
        log.exception(f"FAIL  {name}: {e}")
        return False


def _telegram():
    import telegram_alerts
    telegram_alerts.report()


def _sheets():
    import sheets_sync
    sheets_sync.sync()


def _pwin():
    import pwin_cache
    pwin_cache.refresh_all()


def _toppicks():
    import top_picks
    top_picks.compute(force=True)


def _breadth():
    import breadth
    result = breadth.compute(force=True)
    log.info(f"BREADTH: {result}")
    return result


def _fyers():
    """Append fresh daily bars from the Fyers broker feed when a token exists.

    Runs BEFORE the generic price ingest so the authenticated exchange feed is
    tried first; ingest_prices then fills anything Fyers could not serve. A
    missing/expired token is not an outage: it is logged and the pipeline
    continues on the free fallback sources.
    """
    import ingest_fyers
    result = ingest_fyers.sync_recent(days=15)
    if not result.get("ok"):
        log.info(f"FYERS SKIPPED: {result}")
    else:
        log.info(f"FYERS SYNC: {result.get('written')} bars, "
                 f"{result.get('by_status')}")
    return result


def _prices():
    """Run the price ingest and refuse to log a misleading OK when stale.

    ``_safe`` only sees exceptions. The old chain therefore printed
    ``OK prices`` even when the whole market spine had not advanced. This
    wrapper checks the external session clock after the fetch and raises if the
    expected bar is still missing, so the daily summary reports a failure and
    the operator sees the real state.
    """
    import db
    import ingest_prices
    import data_freshness
    failed = ingest_prices.run(show_every=0)
    conn = db.get_conn()
    try:
        assessment = data_freshness.assess(conn)
    finally:
        conn.close()
    if not assessment.get("fresh"):
        raise RuntimeError(
            f"price spine stale after ingest: {assessment.get('message')}")
    if failed:
        log.warning(f"PRICES PARTIAL: {len(failed)} symbols still failed; "
                    f"market spine is current through "
                    f"{assessment.get('latest')}")
    return {"failed": len(failed or []),
            "latest": assessment.get("latest")}


def run():
    log.info("=" * 50)
    log.info("DAILY UPDATE START")
    results = {}
    results["fyers"] = _safe("fyers", _fyers)
    results["prices"] = _safe("prices", _prices)
    results["technicals"] = _safe(
        "technicals", lambda: __import__("technicals").compute_all())
    # Breadth must be computed after bars exist: it is the second half of the
    # regime gate and was previously only computed lazily inside swing, leaving
    # breadth_daily empty for every other consumer.
    results["breadth"] = _safe("breadth", _breadth)
    # ORDER MATTERS: the scan consumes today's ML scores. Running scan before
    # ml (the old order) silently used yesterday's predictions.
    results["ml"] = _safe(
        "ml", lambda: __import__("ml_predict").predict_all())
    results["scan"] = _safe(
        "scan", lambda: __import__("scan").run())
    results["pwin"] = _safe("pwin", _pwin)
    results["toppicks"] = _safe("toppicks", _toppicks)
    results["events"] = _safe(
        "events", lambda: __import__("events").detect())

    def _swing():
        import swing_live
        swing_live.update_outcomes()
        swing_live.scan()
    results["swing"] = _safe("swing", _swing)

    results["telegram"] = _safe("telegram", _telegram)
    results["sheets"] = _safe("sheets", _sheets)

    ok = sum(1 for v in results.values() if v)
    log.info(f"DAILY UPDATE COMPLETE — {ok}/{len(results)} steps ok")
    log.info("=" * 50)
    return results


if len(sys.argv) > 1 and sys.argv[1] == "run":
    run()