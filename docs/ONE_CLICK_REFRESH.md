# ONE-CLICK REFRESH & LIVE SYSTEM (18 Oct 2026)

Answer to "I cannot give daily time to update the data": **you don't have to.**
There are now two layers:

1. **Automatic** — the VM's scheduler refreshes everything on a timetable and
   the UI reads the database live. You do nothing.
2. **One button** — the ⚡ **Data** panel in the terminal lets you force a full
   refresh any time (phone or laptop) and reloads the page with the new data.

## What is automatic (VM, IST)

| Time | Job |
|---|---|
| 08:10 daily | Fyers token auto-renewal (pin-based) or a single Telegram "login due" note |
| 15:30 | Data-quality checks |
| 15:45 | Early chain (Yahoo-based): prices → technicals → breadth → ML → scan → PWin → Top Picks → events → swing → Telegram |
| 19:30 (Mon–Fri) | **Official NSE EOD**: raw prices + delivery % + every index close from NSE archives (free, no login) |
| 08:15 daily | Official EOD morning retry (repairs any missed evening download) |
| 16:00 | Delivery %
| 16:15 | Swing scan + grading |
| 16:45 | Institutional accumulation |
| 17:30 | FII/DII macro |
| 18:05 / 18:35 | Patterns / DTW templates |
| 19:00 (Mon–Fri) | Trader League live paper league |
| Sat 08:00 / 08:30 | Fundamentals refresh + derive/enrich · governance feed (announcements + pledge) |
| Sat 09:00 | Meta-model retrain |
| Sun 06:00 / 09:00 | Setup-pool rebuild · value radar |
| Mon 08:00 / 1st 10:00 | Monte-Carlo · walk-forward |

The service is **enabled at boot** (`systemctl is-enabled nse-terminal`), so a
VM reboot does not stop it. 21 jobs were verified live.

## What the button does

Press **⚡ Data** (bottom-right, every page) → **Refresh data now**. The server
runs the same chain, in dependency order:

`fyers (if token) → official NSE archives (raw prices + delivery + indices) →
free per-symbol fallbacks → technicals → breadth → ML → scan → PWin → events →
institutional → Top Picks → patterns → templates`

- Measured live on the VM: **12/12 steps OK in 67 seconds** (patterns 19 s,
  templates 6.6 s, prices 30 s when any symbol is behind).
- The panel shows step progress, then **reloads the page** so every view shows
  the refreshed data.
- One run at a time: a second press while running just attaches to the running
  job (no corruption).
- If a step fails the run is recorded as **partial** with the failing step name;
  everything else still lands.
- Every run is audited in the `refresh_runs` table (trigger `ui`/`cli`, steps,
  timings, status).

API (for scripts / a phone shortcut):
```bash
curl -X POST http://140.238.226.249:8000/api/refresh     # start
curl      http://140.238.226.249:8000/api/refresh/status # progress
curl      http://140.238.226.249:8000/api/data/health    # one-shot health
```
Or the CLI equivalent: `python refresh_pipeline.py run` / `status` / `health`.

## What the panel tells you

- **Prices**: last bar date + row count.
- **Data gate**: `fresh` (0 missing sessions) or **STALE — signals paused**
  (the hard freshness gate is blocking writers).
- **Fyers**: connected / token expired / not logged in (optional).
- **Last refresh**: when and with what status.
- If the token is missing, the panel contains the Fyers login flow (open login →
  paste auth code once → save) and an **Auto-renew token** button.

## Is Fyers required?

**No.** Prices refresh automatically from the official NSE archives (plus free
per-symbol fallbacks) (Yahoo/NSE/jugaad) on the
schedule and through the button. Fyers is the *quality upgrade*: an
authenticated exchange feed used for the raw-price rebuild. Without a Fyers
login the system is still live; the only consequence is that the price basis
stays the adjusted-yfinance one until you log in.

## Making Fyers logins rare (optional, free)

Fyers allows a pin-based token refresh: one browser login can be renewed
without a browser for as long as the refresh token is valid (Fyers documents
~15 days). To enable it:

1. Add one line to `.env` on the machine: `FYERS_PIN=<your 4-digit Fyers PIN>`
2. Log in once via the panel / `python fyers_client.py login-url` + `exchange`.
3. From then on the 08:10 job renews the token automatically; if renewal ever
   fails you get one Telegram reminder instead of a silent gap.

Security: `.env` is gitignored and `FYERS_PIN` never leaves the machine; the API
responses never contain the token or the PIN.

## Duplicate-scheduler guard

The VM is the single scheduler owner. A second instance (e.g. the laptop) must
run with `DISABLE_SCHEDULER=1`, otherwise both would execute every job and send
duplicate Telegram alerts. The terminal honours that environment variable.

## If you only want one thing to remember

Open `http://140.238.226.249:8000` on your phone, tap **⚡ Data** → **Refresh
data now** whenever you want. Everything else is already on a timetable.
