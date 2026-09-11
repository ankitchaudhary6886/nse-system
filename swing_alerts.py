"""Telegram alerts for swing setups — text + chart snapshot.
v4: adds ALL-WEATHER setup alert (half size, DEFENSIVE regime)."""
import os


def send(text):
    try:
        import telegram_alerts
        telegram_alerts.send(text)
        return True
    except Exception as e:
        print(f"[ALERT] telegram_alerts failed: {e}")
    try:
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        token = os.getenv("TELEGRAM_TOKEN")
        chat = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat:
            print("[ALERT] telegram creds missing")
            return False
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[ALERT] send failed: {e}")
        return False


def notify_setup(st):
    try:
        import fund_veto
        bad, why = fund_veto.vetoed(st.symbol)
        if bad:
            send(f"🚫 FUND VETO {st.symbol} — setup suppressed\n"
                 f"reason: {why}\n"
                 f"(not tradeable under fundamental gate)")
            print(f"[ALERT] {st.symbol} vetoed: {why}")
            return False
    except Exception as e:
        print(f"[ALERT] veto check skipped: {e}")

    risk = ((st.entry_price - st.stop_loss) / st.entry_price) * 100 \
        if st.entry_price else 0
    text = (f"🏄 NEW SETUP {st.symbol}\n"
            f"Trigger  ₹{st.entry_price}\n"
            f"PDL Stop ₹{st.stop_loss}\n"
            f"Target   ₹{st.target_price}\n"
            f"Risk {risk:.1f}% · PB {st.pullback_depth*100:.0f}%\n"
            f"Shape {st.shape_score}/100 · Zone {st.ema_proximity}")
    ok = send(text)
    try:
        import chart_img
        import telegram_alerts
        path = chart_img.render(
            st.symbol,
            setup={"trigger": st.entry_price,
                   "stop": st.stop_loss,
                   "target": st.target_price})
        if path:
            telegram_alerts.send_photo(
                path, caption=f"📊 {st.symbol} setup chart")
    except Exception as e:
        print(f"[ALERT] chart snapshot skipped: {e}")
    return ok


def notify_all_weather(sym, st):
    """Alert for ALL-WEATHER setups (DEFENSIVE regime, half position size)."""
    try:
        import fund_veto
        bad, why = fund_veto.vetoed(sym)
        if bad:
            send(f"🚫 AW VETO {sym} — {why}")
            return False
    except Exception:
        pass

    risk = st["risk_pct"] * 100
    text = (f"🌧️ ALL-WEATHER SETUP {sym}\n"
            f"Pattern: {st['pattern']}\n"
            f"Trigger  ₹{st['entry']}\n"
            f"Stop     ₹{st['stop']}\n"
            f"Target   ₹{st['target']} (2R)\n"
            f"Risk {risk:.1f}% · Fund score {st.get('fund_score', '—')}\n"
            f"⚠️ DEFENSIVE regime — use HALF position size")
    ok = send(text)
    try:
        import chart_img
        import telegram_alerts
        path = chart_img.render(
            sym,
            setup={"trigger": st["entry"],
                   "stop": st["stop"],
                   "target": st["target"]})
        if path:
            telegram_alerts.send_photo(
                path, caption=f"📊 {sym} ALL-WEATHER chart")
    except Exception as e:
        print(f"[ALERT] AW chart skipped: {e}")
    return ok


if __name__ == "__main__":
    ok = send("🟢 NSE Intelligence Terminal — alert channel test")
    print("sent" if ok else "check logs above")