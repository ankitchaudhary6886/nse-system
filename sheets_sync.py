import sys
import os
import datetime as dt
import db

KEY = "data/gcp_key.json"
SID_FILE = "data/sheet_id.txt"


def _available():
    return os.path.exists(KEY) and os.path.exists(SID_FILE)


def get_sh():
    import gspread
    gc = gspread.service_account(filename=KEY)
    with open(SID_FILE) as f:
        sid = f.read().strip()
    return gc.open_by_key(sid)


def write_tab(sh, title, header, rows):
    ws = None
    for w in sh.worksheets():
        if w.title == title:
            ws = w
    if ws is None:
        ws = sh.add_worksheet(title=title,
                              rows=max(len(rows) + 5, 20),
                              cols=len(header))
    ws.clear()
    ws.append_rows([header] + rows)
    return ws


def sync():
    if not _available():
        print(f"[sheets] skipping — missing {KEY} or {SID_FILE}")
        return 0
    try:
        import gspread  # noqa: F401
    except ImportError:
        print("[sheets] skipping — gspread not installed")
        return 0

    conn = db.get_conn()
    sh = get_sh()

    q = ("SELECT r.symbol, s.name, s.sector, f.current_price, f.pe, "
         "f.roce, f.debt_to_equity, f.profit_growth_3y, "
         "r.fundamental_score, m.final_ml_score, COALESCE(p.status,'') "
         "FROM scan_results r "
         "JOIN stocks s ON s.symbol=r.symbol "
         "LEFT JOIN fundamentals f ON f.symbol=r.symbol "
         "LEFT JOIN ml_predictions m ON m.symbol=r.symbol "
         "AND m.prediction_date=(SELECT MAX(prediction_date) "
         "FROM ml_predictions) "
         "LEFT JOIN pipeline p ON p.symbol=r.symbol "
         "WHERE r.scan_date=(SELECT MAX(scan_date) FROM scan_results) "
         "ORDER BY r.fundamental_score DESC")
    rows = [list(r) for r in conn.execute(q).fetchall()]
    header = ["Symbol", "Name", "Sector", "Price", "PE", "ROCE", "D/E",
              "Profit3Y", "FundScore", "MLScore", "Status"]
    write_tab(sh, "Scores", header, rows)

    rec = [r for r in rows if r[10] == "Recommended"]
    write_tab(sh, "Recommended", header, rec)

    prows = [list(r) for r in conn.execute(
        "SELECT symbol, status, added_date, reason, notes "
        "FROM pipeline ORDER BY status").fetchall()]
    write_tab(sh, "Pipeline",
              ["Symbol", "Status", "Added", "Reason", "Notes"], prows)

    write_tab(sh, "SyncLog", ["Time", "Scores", "Recommended"],
              [[dt.datetime.now().isoformat(), len(rows), len(rec)]])
    print(f"Sheets synced: {len(rows)} scores | {len(rec)} recommended")
    conn.close()
    return len(rows)


if __name__ == "__main__":
    sync()