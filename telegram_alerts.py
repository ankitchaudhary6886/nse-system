"""Telegram alerts — token loaded from data/tg_secret.txt (never hardcoded)."""
import os
import sys
import requests
import db

SECRET = "data/tg_secret.txt"


def load():
    """Return (token, chat_id): env vars if set, else the secret file."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        return token, chat
    with open(SECRET, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    return lines[0], lines[1]


def send(text):
    token, chat = load()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat, "text": text},
                      timeout=20)
    print("telegram:", r.status_code)
    return r.status_code == 200


def report():
    conn = db.get_conn()
    last = conn.execute(
        "SELECT MAX(scan_date) FROM scan_results").fetchone()[0]
    lines = ["📊 NSE SYSTEM DAILY REPORT", f"Scan date: {last}"]
    passed = conn.execute(
        "SELECT COUNT(*) FROM scan_results "
        "WHERE scan_date=? AND passed=1", (last,)).fetchone()[0]
    lines.append(f"Passed gates: {passed}")
    rec = conn.execute(
        "SELECT symbol FROM pipeline "
        "WHERE status='Recommended' LIMIT 10").fetchall()
    lines.append("RECOMMENDED: " +
                 (", ".join(r[0] for r in rec) if rec else "none"))
    top = conn.execute(
        "SELECT symbol, final_ml_score FROM ml_predictions "
        "ORDER BY final_ml_score DESC LIMIT 5").fetchall()
    lines.append("TOP ML: " +
                 ", ".join(f"{s} {v:.0f}" for s, v in top))
    send("\n".join(lines))
    conn.close()


if len(sys.argv) > 1:
    if sys.argv[1] == "test":
        send("✅ NSE system connected")
    elif sys.argv[1] == "report":
        report()