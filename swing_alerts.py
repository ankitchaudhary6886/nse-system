"""Telegram alerts — auto-discovers bot credentials."""
import os
import requests

def _creds():
    token = None
    chat = None
    try:
        import telegram_alerts as ta
        for name in dir(ta):
            if name.startswith("__"):
                continue
            val = getattr(ta, name)
            if not isinstance(val, str):
                continue
            up = name.upper()
            if token is None and "TOKEN" in up:
                token = val
            if chat is None and ("CHAT" in up or "USER_ID" in up):
                chat = val
    except Exception:
        pass
    token = token or os.getenv("TELEGRAM_TOKEN")
    chat = chat or os.getenv("TELEGRAM_CHAT_ID")
    return token, chat

def send(text):
    token, chat = _creds()
    if not token or not chat:
        print("[ALERT] telegram creds missing")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text}, timeout=10)
        ok = r.status_code == 200
        if not ok:
            print(f"[ALERT] telegram HTTP {r.status_code}: {r.text[:120]}")
        return ok
    except Exception as e:
        print(f"[ALERT] send failed: {e}")
        return False

def notify_setup(st):
    risk = ((st.entry_price - st.stop_loss) / st.entry_price) * 100 \
        if st.entry_price else 0
    text = (f"🏄 NEW SETUP {st.symbol}\n"
            f"Trigger  ₹{st.entry_price}\n"
            f"PDL Stop ₹{st.stop_loss}\n"
            f"Target   ₹{st.target_price}\n"
            f"Risk {risk:.1f}% · PB {st.pullback_depth*100:.0f}%\n"
            f"Shape {st.shape_score}/100 · Zone {st.ema_proximity}")
    return send(text)

if __name__ == "__main__":
    ok = send("🟢 NSE Intelligence Terminal — alert channel test")
    print("sent" if ok else "FAILED")