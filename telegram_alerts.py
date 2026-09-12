"""
Thin shim — delegates to alerts.py. Kept for backwards compatibility.
New code should `import alerts` directly.
"""
from alerts import send, send_photo, report

__all__ = ["send", "send_photo", "report"]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        send("✅ telegram_alerts shim works")
    elif len(sys.argv) > 1 and sys.argv[1] == "report":
        report()
    else:
        print("usage: python telegram_alerts.py [test|report]")