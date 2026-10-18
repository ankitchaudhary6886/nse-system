# FREE, EFFORTLESS DAILY DATA — SOURCE OPTIONS AND THE CHOSEN STACK

Owner constraint: **zero cost, no daily intervention, one-time build.** Fyers is
optional, not required. This note lists every realistic free option, what each
is good for, and the stack the system now uses automatically.

## 1. Options compared

| Source | Cost / auth | What it gives | Reachable from the Oracle VM? | Verdict |
|---|---|---|---|---|
| **NSE official archives** (`nsearchives.nseindia.com`) | Free, **no auth/API key** | Raw daily OHLCV for every NSE equity (`sec_bhavdata_full_DDMMYYYY.csv`), delivery qty/%, every index close (`ind_close_all_DDMMYYYY.csv`), official security master (`EQUITY_L.csv`), **historical daily bhavcopy zips** back to old years (`.../YYYY/MMM/cmDDMMMYYYYbhav.csv.zip`) | **YES** — verified 18 Oct 2026 from the VM: files returned 200 (`sec_bhavdata_full` 397 KB, `ind_close_all` 17.5 KB, `EQUITY_L` 184 KB, a 2021 legacy zip 77 KB) | **CHOSEN — primary** |
| Fyers API v3 | Free with a Fyers account; daily OAuth unless a PIN-based refresh token is configured | Exchange-grade history/quotes/depth, index tickers; raw prices | Yes, after login | **Optional upgrade** (system works without it) |
| Yahoo / yfinance | Free, no auth | Adjusted OHLCV, some fundamentals, splits/dividends | Mostly; rate-limits/crumb issues, currently the 15:45 fallback | **Fallback + corporate-action candidates** |
| NSE website JSON APIs (announcements, shareholding) | Free, no key | Announcements, shareholding | **NO** — blocks cloud IPs; works from the home laptop | Used weekly via the laptop/bundle; never a daily dependency |
| BSE bhavcopy | Free, no auth | BSE equity EOD | usually yes | Possible second mirror (not wired yet; NSE archive is sufficient) |
| jugaad-data / nseindiaapi / nsemine / pnsea / nsetools | Free scrapers/unofficial mirrors | OHLCV | partly | Kept as per-symbol price fallbacks only |
| Alpha Vantage / TwelveData / EODHD free tiers | Free tiers but API keys, limited calls, incomplete NSE coverage | — | — | Rejected: keys + quotas + gaps |
| TrueData / ScanX / Screener paid feeds | Paid | Point-in-time fundamentals etc. | — | Out of scope (owner: no spend) |

## 2. What is now automatic (one-time build, no intervention)

| IST time | Job | Source |
|---|---|---|
| 08:15 daily | Official EOD morning retry/catch-up | NSE archives |
| 08:10 daily | Fyers token auto-renew (only if configured) | Fyers (optional) |
| 15:30 | Data-quality checks | local DB |
| **15:45** | Yahoo-based early chain: prices → technicals → breadth → ML → scan → PWin → Top Picks → events → swing → Telegram | Yahoo/NSE mirrors |
| **19:30 Mon–Fri** | **Official NSE EOD: raw prices + delivery% + all index closes** (catch-up up to 7 days) | NSE archives |
| 18:05 / 18:35 | Patterns / templates | local DB |
| Sat 08:00 / 08:30 | Fundamentals refresh → derive/enrich · governance (announcements + pledge) | free sources |

Plus the ⚡ **Refresh now** button runs the same chain on demand, official
source first, and reloads the page.

A missing archive file is treated as an **exchange holiday** (recorded as
`holiday`), never as stale data, and catch-up is idempotent — a missed evening
is repaired automatically the next morning.

## 3. What this fixes that Fyers was needed for

- **Raw price basis without a login.** Official bhavcopy prices are unadjusted;
  every adopted symbol gets `price_meta.basis='nse_bhavdata_raw'`. A full raw
  history rebuild is now possible entirely from free archives:
  `python nse_eod_ingest.py history --from 2021-08-17 --to 2026-10-16 --apply`
  (probe first without `--apply`; it writes a one-time backup table).
- **Delivery %** fills `delivery_daily` — the 15% delivery weight in Top Picks is
  no longer dead.
- **Index series** fill `index_daily` (NIFTY50/500/BANK + sectors) — the basis
  for breadth denominators / RS / beta is now stored locally (wiring those
  consumers to `index_daily` is the next improvement; current regime still uses
  a live Yahoo index call).
- **Historical verification** for free: the legacy archive zips let us
  cross-check or replace any old date range.

## 3b. "Old history is still adjusted" — what that means and how it was fixed

`yfinance` returns **back-adjusted** prices: when a stock splits 1:10 or pays a
big dividend, yfinance rewrites every older price so the series has no jump. The
exchange's official file, by contrast, is **raw** — it prints what actually
traded that day. Mixing the two silently creates fake gaps at the join.

The one-time rebuild replaces the whole 2021-08 → 2026-10 range with the official
raw `sec_bhavdata_full` files (verified available for every year):
`python nse_eod_ingest.py history --from 2021-08-17 --to 2026-10-16 --apply`
It backs up the current table first, writes raw OHLCV, and relabels
`price_meta.basis` (`nse_bhavdata_raw` when the symbol's history is fully raw,
`mixed_adjusted_then_raw` when older rows remain). Re-run the chain afterwards
(technicals → ML → scan → PWin → patterns → Top Picks) because every indicator
now sits on the raw basis.

### Rebuild result (executed 18 Oct 2026, live VM)

| Metric | Value |
|---|---|
| Official dates rebuilt (2021-08-17 → 2026-10-16) | **1,336** sessions |
| Rows written | **825,558** |
| Holidays (no archive file, correctly skipped) | 12 |
| Malformed archive file | **1** date (2022-08-08) kept on the old bar |
| Backup table | `prices_daily_adj_backup_20261018_184231` |
| Symbols on raw basis after rebuild | **859** (3 symbols had no official rows and keep their old bars) |
| Total price rows / distinct symbols | 868,883 / 862 |
| Chain recomputed after rebuild | ✓ technicals, breadth, ML, scan, PWin, events, institutional, Top Picks, patterns, templates (all OK) |

The laptop copy was replaced with the rebuilt database and is live again.

**Fyers' role after this:** it is NOT the daily source. It fills what the free
archives cannot: a symbol missing from a day's bhavcopy, a date whose archive
file is unavailable, odd series/renamed tickers the archives do not map, and
historical stretches you explicitly ask for. `backfill_gaps.py` only writes
dates that are missing, never overwrites official bars, and labels such symbols
`mixed_raw_sources`. Commands:
`python backfill_gaps.py report` · `fill [--days N] [--apply]` ·
`history --from … --to … [--symbols …] [--apply]`.

## 4. Honest limitations

1. Archives publish in the evening; the 15:45 chain is an early estimate and the
   19:30 official pull is the authority. The UI shows price dates, so this is
   visible, not silent.
2. Official prices are **raw**; corporate actions are not applied. A symbol that
   already has adjusted history becomes `mixed_adjusted_then_raw` until the raw
   history rebuild is run. Corporate-action candidates still come from the free
   yfinance split/dividend lists (and the manual CSV), so the repair factor is
   known when a gap appears.
3. Interactive NSE endpoints (announcements/shareholding) block the VM's cloud
   IP. The weekly governance job degrades gracefully; the home laptop can fetch
   and the data is transferable.
4. No intraday/tick data — deliberately, the system is daily-bar.

## 5. One-time setup (already done)

- Code: `nse_eod_ingest.py` (fetchers/parsers/writers/CLI), scheduled jobs,
  ⚡ refresh integration, 12 offline tests.
- Tables: `nse_eod_sync` (per-date audit), `index_daily`, `nse_security_master`
  (+ existing `delivery_daily`/`prices_daily`/`price_meta.basis`).
- Commands if you ever want to run manually:
  `python nse_eod_ingest.py master` (also `repair-basis [--apply]` to relabel
  mixed provenance) · `catchup --days 15` · `report` ·
  `history --from … --to … [--apply]`.
