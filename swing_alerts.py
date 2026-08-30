"""Telegram alert the moment a new swing setup fires."""
import os
import requests

def _creds():
    try:
        import telegram_alerts as ta
    except Exception:
        ta = None
    token = (os.getenv("TELEGRAM_TOKEN")
             or getattr(ta, "TOKEN", None)
             or getattr(ta, "BOT_TOKEN", None))
    chat = (os.getenv("TELEGRAM_CHAT_ID")
            or getattr(ta, "CHAT_ID", None)
            or getattr(ta, "CHAT", None))
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
        return r.status_code == 200
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