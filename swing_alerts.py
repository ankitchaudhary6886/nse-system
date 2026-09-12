"""
Thin shim — delegates to alerts.py. Kept for backwards compatibility.
New code should `import alerts` directly.
"""
from alerts import send, notify_setup, notify_all_weather

__all__ = ["send", "notify_setup", "notify_all_weather"]


if __name__ == "__main__":
    ok = send("🟢 swing_alerts shim works")
    print("sent" if ok else "failed")