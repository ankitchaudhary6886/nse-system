# Fyers Integration — Market Data Only

Status: built, reviewed, hardened and **deployed to the live VM (18 Oct, commit 8308f41)**; the whole project suite is 230 tests green. **No Fyers token yet, so no live bars have been fetched** — every price in the DB is still the adjusted yfinance legacy basis. App type: **Non-trading**. App ID: `2DA83NVOJU-100`.

| File | Job |
|---|---|
| `fyers_client.py` | Hand-written Fyers API v3 client (no SDK), OAuth login + token store, CLI: `login-url`, `exchange`, `status`, `probe`, `screeners`, `clear` |
| `ingest_fyers.py` | Ingestion into `data/app.db`: `status`, `master`, `history`, `quotes`, `verify`, `sync` |
| ~~`data_sources/adapters/fyers.py`~~ | **Removed after independent review**: it created a second, unguarded write path into `prices_daily`. Fyers now writes **only** through `ingest_fyers.py` — exactly one guarded writer |
| `daily_update.py` | New **first** pipeline step `fyers` → `ingest_fyers.sync_recent(days=15)` |
| `db.py` | Tables `fyers_symbol_master`, `fyers_quotes`, `fyers_sync_log` |
| `test_fyers_integration.py` | 40 tests, fully offline (fake HTTP session — no network, no token) |

## 1. What this is — and what it is not

**It is** a *data* client. It calls Fyers' read-only market-data endpoints and writes history, quotes and a symbol master into our own SQLite database. It is the only source here that is an authenticated broker feed: same exchange, no scraping, no HTML parsing, no rate-limit lottery.

**It is not** a trading integration. The Fyers app is registered as type **Non-trading** and **no order, position, holdings, fund or margin endpoint is called anywhere in this repo**. Nothing here can place, modify or cancel an order.

### What Fyers gives us

| Capability | Endpoint used | Where it lands |
|---|---|---|
| Daily OHLCV history (`1D` resolution used here) | `GET /data/history` | `prices_daily` + `price_meta` |
| Quote snapshots (50 symbols per request, chunked) | `GET /data/quotes` | `fyers_quotes` |
| Market depth (bid/ask book + OHLCV flag) | `GET /data/depth` | on demand (probe/diagnostics) |
| Exchange market status | `GET /data/marketStatus` | printed by `status` |
| Official NSE cash symbol master (public CSV, **no auth**) | `https://public.fyers.in/sym_details/NSE_CM.csv` | `fyers_symbol_master` |
| Account profile (token health check) | `GET /api/v3/profile` | printed by `status` |
| Screener config / query | `GET /api/v3/screeners/config`, `POST /api/v3/screeners/query` | probe only — **entitlement dependent** |

### What Fyers does **not** give us

| Missing here | Still owned by |
|---|---|
| Fundamentals (PE, ROE, debt, growth) | TradingView / ScanX / filings pipeline already in the repo |
| Delivery % / deliverable quantity | NSE bhavcopy pipeline |
| FII / DII flows | existing macro ingestion |
| Corporate-action calendar (splits, dividends, bonus) | filings / other sources — **this is why we do the seam check (§6)** |
| Adjusted (split/dividend-adjusted) prices | we get **raw** prices; our store holds yfinance `auto_adjust=True` history |

The screener API is entitlement-dependent: without access it returns an error envelope. Probe with `python fyers_client.py screeners` and read a failure as "not entitled", not as a bug.

## 2. One-time setup (laptop)

### 2.1 Create / verify the app on the Fyers API dashboard

1. Log in to `myapi.fyers.in` with the trading account.
2. Confirm the app exists; note the **App ID** (`2DA83NVOJU-100`) and the **Secret ID**.
3. Set the app's **Redirect URI** to exactly `https://fyers.in`, app type **Non-trading**. One differing character between dashboard and `FYERS_REDIRECT_URI` breaks login with a redirect-URI error.

### 2.2 Fill `.env` (gitignored — never committed)

`.env` lives at the project root and is ignored by `.gitignore`:

```
FYERS_APP_ID=2DA83NVOJU-100
FYERS_SECRET_ID=<from Fyers API dashboard>
FYERS_REDIRECT_URI=https://fyers.in
```

`FYERS_ACCESS_TOKEN` is optional: if set it overrides the token file (handy for a throwaway token in a shell). The normal path is the token file below.

### 2.3 Daily login (once per trading day)

Fyers tokens die at ~**06:00 IST**; we store a **05:55 IST** expiry so the client stops using a token five minutes before the broker does. Renew once per trading day, before the first ingest.

```powershell
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\Activate.ps1
python fyers_client.py login-url
```

Open the printed URL in a browser, log in, approve the app. The browser lands on `https://fyers.in/?auth_code=<CODE>&state=nse_system` (the page itself may be blank). **Copy the `auth_code`** from the address bar — or copy the whole URL, the client accepts either and extracts the code itself. Then exchange it (auth codes are **single-use** and short-lived):

```powershell
python fyers_client.py exchange --code '<PASTE_AUTH_CODE>'
```

Success looks like:

```
token stored: 2026-10-19T05:55:00+05:30 IST
profile: <account display name>
```

- `token stored:` — the expiry we will honour; `profile:` — a live `/api/v3/profile` call proving the token works.
- Token file is `data/fyers_token.json` (gitignored by the `data/*token*` rule) holding `access_token`, `refresh_token`, `issued_at`, `expires_at`, `profile`. **Never** paste its contents into chat, a commit, or a log.
- `exchange` with no `--code` prompts for a pasted value. Run this once per trading day: a missing/stale token is not an outage (§3).

## 3. Daily operation

```
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\Activate.ps1
python ingest_fyers.py sync
```

`sync` does this, in order:

1. **Symbol master** — refreshes `fyers_symbol_master` only if it is empty or older than 7 days (`MASTER_STALE_DAYS`). The CSV is public, no token needed.
2. **Universe resolution** — maps the combined universe (`band_universe` ∪ `active_universe`, 1,349 symbols today) to Fyers tickers: exact match → `_`→`-` normalisation → `.XX` suffix → known series suffixes (`-SM`, `-BE`, `-BZ`, `-ST`, `-RR`, `-IV`, `-MF`, `-N1`) → ISIN join via `scanx_fundamentals_snapshots`. Unresolved symbols are **reported, never guessed**.
3. **History append** — for symbols whose last bar is behind the market's latest close, fetch the last 15 days plus overlap, run the seam check and bar validation, then append only dates newer than the stored last date.

Output shape (abridged):

```json
{
  "universe": {"total": 1349, "resolved": 1347, "unresolved": 2,
               "by_method": {"exact": 1293, "normalized": 54},
               "unresolved_sample": ["HEG", "SSFLPP.E1"]},
  "history": {"symbols": 1347, "written": 1347, "ok": 1345, "dry_run": false,
              "by_status": {"ok": 1345, "up_to_date": 2},
              "seam_mismatches": [], "errors": []}
}
```

`"master"` appears only on runs where the master was refreshed. `by_status` values: `ok`, `up_to_date`, `no_data`, `no_overlap`, `seam_mismatch`, `no_valid_bars`, `dry_run`, `error`.

**Wiring in `daily_update.py`:** `results["fyers"] = _safe("fyers", _fyers)` runs before `results["prices"]`. `sync_recent()` **never raises**: no token → `{"ok": false, "skipped": "no fyers token"}`, auth failure → `{"ok": false, "auth_error": ...}`, logged as `FYERS SKIPPED: {...}`; success logs `FYERS SYNC: <n> bars, {...by_status}`. `ok` is true only when at least one resolved symbol received new bars (or every resolved symbol was already up to date), so a total no-op cannot log as success. Then the pipeline continues on the free Yahoo / NSE / jugaad sources. **Until a token exists nothing breaks** because `sync_recent` returns before any HTTP call. **Fyers is deliberately NOT in the generic `ingest_prices.py` provider chain** (review finding): that path writes whatever a provider returns into `prices_daily` without seam/validation guards, so the only writer for broker bars is `ingest_fyers.py`. `ingest_prices` still fills the dates Fyers could not serve, from the free sources.

## 4. First-time backfill (in this order)

```
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\Activate.ps1
python ingest_fyers.py master
python ingest_fyers.py verify --limit 20 --days 10
python ingest_fyers.py history --days 30
python ingest_fyers.py history --mode rebuild --symbols <PASTE_SEAM_SYMBOLS>
python ingest_fyers.py verify --limit 20 --days 10
```

1. **`master`** — imports the NSE cash master. Measured on the real 2026-10-16 master: **10,116 rows**. Output `{"parsed": 10116, "new": ..., "updated": ..., "source_updated": "2026-10-16"}`.
2. **`verify --limit 20`** — cross-source proof *before* writing: fetch 20 symbols from the broker and compare against stored bars on overlapping dates. Verdicts: `match`, `mostly_match`, `mismatch`, `adjustment_mismatch`, `no_overlap`, `error`. You want `match`/`mostly_match`.
3. **`history --days 30`** — append-only backfill. On the laptop the universe is 1,347 symbols (~8–10 min); on the live VM it is 864 symbols. The binding limit is the client's 180 requests/minute cap, not 8/second.

   After the append, `python rebuild_raw_history.py plan` prints the honest raw-migration budget. On the VM (18 Oct): **864 symbols, ~6,912 API calls, ~38 minutes** at 180 req/min, with every symbol on the legacy adjusted basis.
4. **`history --mode rebuild --symbols ...`** — only the symbols the previous command listed under `SEAM MISMATCH` / `SEAM_GAP_SUSPECT` / `NO_OVERLAP`.
5. **`verify --limit 20` again** — after rebuilds the same 20 symbols should read `match`.

   For the full raw migration use the orchestrator instead of a loop by hand:

   ```powershell
   python rebuild_raw_history.py plan                 # read-only budget
   python rebuild_raw_history.py run --limit 10       # dry run pilot
   python rebuild_raw_history.py run --apply --limit 10
   python rebuild_raw_history.py verify --limit 20
   ```

   `run` is dry by default and refuses without a token; `--apply` warns that every downstream artifact (technicals, scans, ML, patterns, Top Picks, backtests) must be recomputed because the price basis changes. `plan` also reports `mixed_pending`: symbols whose pre-5-year rows survive a rebuild end up `mixed_adjusted_then_raw` and are a human decision, not a blind retry.

### What "SEAM MISMATCH" means (plain English)

Our stored history came from yfinance `auto_adjust=True`, which **back-adjusts** old prices for splits and dividends (a 1:10 split divides old closes by 10). Fyers gives **raw, unadjusted** prices. Appending raw onto adjusted history creates a fake jump at the join date that no chart can tell apart from a real crash. So every sync re-fetches an overlap window (from 15 days before the last stored bar, so ~10 trading days usually overlap) and measures the **ratio** on shared dates:

- median ratio within **±2%** (`SEAM_TOLERANCE`) → same basis, append;
- median ratio outside **±2%** (individual dates off by more than 0.5%) → status **`seam_mismatch`**, the symbol is **not appended**, and a `seam_mismatch` row is written to `fyers_sync_log`.

There is one more seam nobody can see in the overlap: a corporate action **after** the last stored bar. Overlap dates all sit before it, so the ratio stays ~1. The remaining fingerprint is the jump between the last stored close and the first new broker close — anything over **15%** is treated as `seam_gap_suspect` and blocked. Anything smaller (a small dividend adjustment) is undetectable without a corporate-action calendar; that is exactly why the long-term fix is a full raw rebuild (Option A in the audit) rather than eternal appending.

The fix is explicit and backed up: `--mode rebuild` writes `data/backups/fyers_rebuild_<SYMBOL>_<YYYYmmdd_HHMMSS>.csv` first, then replaces only the fetched window and **keeps older rows outside it**. It refuses to run when the broker returns fewer than 60% of the bars the store already holds in that window (`rebuild_shrunk`) — a truncated fetch must never delete history. It also records the price basis in `price_meta.basis`: `fyers_raw`, `mixed_adjusted_then_raw`, or NULL (legacy adjusted). `--force` deliberately overrides these guards — do not use it casually.

## 5. Diagnostics

### `python ingest_fyers.py status` (no token required; degrades instead of failing)

| Field | Meaning |
|---|---|
| `credentials.app_id` | App ID from `.env` (the secret value is never printed) |
| `credentials.token` | `token_file`, `present`, `issued_at`, `expires_at`, `expired` — from `data/fyers_token.json` |
| `prices_latest_date` / `prices_stale_days` | Newest date in `prices_daily` overall, and days behind today (IST) |
| `symbol_master.rows` | Rows in `fyers_symbol_master` (expect ~10,116) |
| `symbol_master.source_updated` / `age_days` | Date printed inside the broker CSV, and age of our import |
| `quotes.rows` / `quotes.latest_ts` | Size and freshness of the `fyers_quotes` audit trail |
| `last_sync_log` | The 5 latest `fyers_sync_log` rows (`run_at`, `kind`, `status`, `symbols`, `rows`) |
| `token_valid` | Live `/api/v3/profile` check — the only field proving the token works *right now* |

`python fyers_client.py status` is the human-readable variant: one `credentials:` line (`app_id=... secret=set|MISSING redirect=...`), the token JSON, then `profile:` and `marketStatus:` lines. Exit codes: `0` ok, `1` no token, `2` profile rejected.

### Test one symbol — `probe`

```
python fyers_client.py probe SBIN
```

Prints the resolved ticker (`NSE:SBIN-EQ`), how many daily candles exist in the last 15 days, the last five normalized bars, and the normalized quote. Zero candles usually means the wrong series (`-EQ` vs `-BE`/`-BZ`/`-SM`) or a delisted/suspended scrip — check `fyers_symbol_master` for what the exchange publishes. Extras: `screeners` (entitlement probe), `clear` (delete token file).

## 6. Safety and provenance rules (enforced in code)

1. **One guarded writer.** Only `ingest_fyers.py` writes broker bars; there is no unguarded adapter path into `prices_daily`. Append is the only default mode. `--mode rebuild` is opt-in, writes `data/backups/fyers_rebuild_*.csv` first, keeps rows outside the fetched window, and refuses a shrunken fetch (`rebuild_shrunk`).
2. **No bar written without validation.** Each bar needs finite positive OHLC, `high >= low`, close inside `[low × 0.98, high × 1.02]`, non-negative volume, and a daily move ≤ **60%** vs the previous accepted close. Rejected bars are counted in `skipped_invalid` and never inserted.
3. **No today's bar before the close** — today's candle is accepted only after 15:40 IST, so a mid-session sync cannot freeze a half-formed bar.
4. **`--dry-run` writes nothing** — no price rows, no sync-log rows; it reports what *would* be written.
5. **Audit trail.** `fyers_sync_log` gets one row per operation (`run_at`, `kind`, `status`, `symbols`, `rows`, `error`, `detail`); every quote keeps the broker's raw JSON in `fyers_quotes.raw_json`, so an audit can prove what the broker actually said. Normalized columns are derived from that payload and never invented.
6. **Rate limits respected locally.** Documented broker limits are 10 req/s, 200 req/min, 100k req/day; we cap at **8 req/s and 180 req/min** and refuse to hammer. Retries (2, i.e. 3 attempts, 1s/2s backoff) only for HTTP 429 and network errors. `401`/`403` or broker codes `-16`/`-17` raise `FyersAuthError` immediately.
7. **Token is gitignored.** `data/fyers_token.json` matches `data/*token*`; `.env` has its own rule. Neither is ever committed.
8. **No order endpoints.** No `/orders`, `/positions`, `/holdings`, `/funds` or `/tradebook` call exists anywhere in the codebase — read-only by construction.

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `No Fyers token. Run: python fyers_client.py login-url` (exit 1) | Never logged in here, or `data/fyers_token.json` was deleted | Run the login flow (§2.3) |
| `"expired": true`, or daily log `FYERS SKIPPED: {'skipped': 'no fyers token'}` | Token passed its 05:55 IST expiry (broker dies ~06:00 IST) | Re-run `login-url` + `exchange` once per trading day |
| `AUTH FAILED: ... (HTTP 401)`, broker code `-16` (invalid token) or `-17` | Token invalidated by a second login, a password change, or a stale file | `python fyers_client.py clear`, then log in again |
| `token exchange FAILED: ... code=-437` | Auth code is **single-use** and short-lived — already used, or too much time passed | Re-run `login-url`, copy a **fresh** code, exchange immediately |
| App-hash / invalid-app-credentials error although the code is definitely fresh | `FYERS_SECRET_ID` mismatch. **Real risk here:** the secret was originally transcribed from a screenshot, where letter **O** vs digit **0** (and `I` vs `1`) look identical — one wrong character breaks the SHA-256 app hash | Re-check `FYERS_SECRET_ID` character by character against the dashboard (copy-paste, do not retype), keep it out of chat/logs, re-run `exchange` |
| Login redirects to a `redirect_uri` error page | App redirect URI ≠ `FYERS_REDIRECT_URI` | Make both exactly `https://fyers.in` |
| `FYERS ERROR: broker rate limit hit (code=-429)` | Broker 429 despite our limiter (e.g. another process using the same app) | Wait ~60s and retry; the client already retried twice with backoff. Never run two ingests at once |
| `no_data` / zero candles from `probe` | Wrong series (`-EQ` vs `-BE`/`-BZ`/`-SM`), or delisted/suspended | Look the symbol up in `fyers_symbol_master`; if absent it is genuinely not in the NSE cash master |
| `SEAM MISMATCH` / `SEAM_GAP_SUSPECT` / `NO_OVERLAP` (not appended) | Adjusted (yfinance) vs raw (Fyers) basis around a split/dividend, a corporate action after the last stored bar, or no provable overlap | `python ingest_fyers.py history --mode rebuild --symbols <symbols>` (backup automatic), then `verify` again. Never use `--force` without checking the corporate-action calendar |
| `REBUILD_SHRUNK` | The broker returned far fewer bars than the store holds in the requested window (truncated fetch/suspension) | Investigate before repeating; history is untouched. `--force` only if the shrink is real |
| `python -m unittest test_fyers_integration` fails | A guard was changed (seam tolerance, bar validation, rate limiter, token expiry). The suite is fully offline, so failures are real logic changes, not network flakiness | Run with `-v`, read the failing assertion, fix the code — do not "fix" the test unless the behaviour change was intentional |

## 8. VM / production rollout (owner rule R47 — whole copy-paste blocks)

Copy one block at a time. Each block starts with `cd`, one command per line, expected output after it. Values you must paste yourself are marked `<PASTE_...>`.

### Block 1 — Laptop: commit and push (`.env` is NOT committed)

```powershell
cd C:\Users\Ankit\Desktop\nse_system
git add fyers_client.py ingest_fyers.py fundamentals_derive.py data_audit.py test_fyers_integration.py db.py daily_update.py docs/
git status --short
git commit -m "Fyers API v3 data integration: client, guarded ingest, tests, docs, audit"
git push
```

Expected: `git status --short` lists only those files (never `.env`, never `data/fyers_token.json`); commit prints `[main 1234abc] Fyers API v3 data integration: ...`; push reports `main -> main`. `requirements.txt` is unchanged by this feature (requests + pandas only).

### Block 2 — Laptop: SSH to the VM and pull

```powershell
cd C:\Users\Ankit\Desktop\nse_system
ssh -i C:\Users\Ankit\.ssh\nse.pem ubuntu@140.238.226.249
cd ~/nse-system
git pull
```

Expected: `ubuntu@...:~$` prompt, then `Already up to date.` or a fast-forward listing `fyers_client.py`, `ingest_fyers.py`, `test_fyers_integration.py`, `db.py`, `daily_update.py`, `docs/FYERS_INTEGRATION.md`.

### Block 3 — VM: create `.env` (no secret in this document)

```bash
cd ~/nse-system
export EDITOR=nano
nano .env
```

Paste these lines, replacing the placeholder **in the editor** (never in a chat window):

```
FYERS_APP_ID=2DA83NVOJU-100
FYERS_SECRET_ID=<PASTE_FYERS_SECRET_ID_FROM_DASHBOARD>
FYERS_REDIRECT_URI=https://fyers.in
```

Save with `Ctrl+O`, `Enter`, exit with `Ctrl+X`. Then verify without printing the secret:

```bash
cd ~/nse-system
chmod 600 .env
grep -c '^FYERS_' .env
grep '^FYERS_APP_ID=' .env
```

Expected: `3` then `FYERS_APP_ID=2DA83NVOJU-100`. If `.env` already exists for other integrations, append the FYERS lines instead of replacing the file.

### Block 4 — VM: dependencies and service restart

```bash
cd ~/nse-system
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart nse-terminal
sudo systemctl status nse-terminal --no-pager | head -5
```

Expected: `Requirement already satisfied` lines (requests/pandas already present — this feature adds no dependency), then `Active: active (running)` with a recent `Main PID` for `nse-terminal.service`.

### Block 5 — VM: log in once for today

```bash
cd ~/nse-system
source venv/bin/activate
python fyers_client.py login-url
```

Expected: one long `https://api-t1.fyers.in/api/v3/generate-authcode?...client_id=2DA83NVOJU-100...` URL, then `Open the URL, approve the app, then copy the auth_code parameter from the redirected URL.` Open it in the **laptop** browser, approve, copy `auth_code` from the address bar, then:

```bash
cd ~/nse-system
source venv/bin/activate
python fyers_client.py exchange --code '<PASTE_AUTH_CODE>'
```

Expected: `token stored: 2026-10-19T05:55:00+05:30 IST` then `profile: <account display name>`. (`data/fyers_token.json` is gitignored on the VM too.)

### Block 6 — VM: master, cross-check, backfill, daily sync

```bash
cd ~/nse-system
source venv/bin/activate
python ingest_fyers.py master
python ingest_fyers.py verify --limit 20 --days 10
python ingest_fyers.py history --days 30
python ingest_fyers.py sync
```

Expected: `master` → `{"parsed": 10116, "new": 10116, "updated": 0, "source_updated": "<date>"}` (split differs if a master already exists); `verify` → `{"checked": 20, "verdicts": {"match": ...}}` with any non-`match` line printed underneath (investigate, do not ignore); `history --days 30` → progress lines `[25/1347] SBIN: ok (+N)` then a JSON summary with `by_status`/`seam_mismatches`/`errors`, taking ~8–10 minutes; `sync` → JSON with `universe` and `history`.

If `seam_mismatches` is non-empty, rebuild exactly those (the only pasted value in the rollout):

```bash
cd ~/nse-system
source venv/bin/activate
python ingest_fyers.py history --mode rebuild --symbols <PASTE_SEAM_SYMBOLS>
```

Expected: a summary with `by_status` `{"ok": N}` and backup CSVs appearing under `data/backups/fyers_rebuild_*.csv`.

### Block 7 — Verification (service, logs, tests, status)

```bash
cd ~/nse-system
source venv/bin/activate
sudo systemctl status nse-terminal --no-pager | head -5
sudo journalctl -u nse-terminal -n 300 --no-pager | grep -i fyers
python -m unittest test_fyers_integration -v
python ingest_fyers.py status
```

Expected: `Active: active (running)`; a `FYERS SYNC: <n> bars, {...}` line (a pre-login `FYERS SKIPPED:` is also healthy); `Ran 40 tests` / `OK`; and a `status` JSON with `"present": true`, a future `expires_at`, `"token_valid": true`, `symbol_master.rows` ≈ 10,116.

## 9. Rollback

Both rollbacks are one-line edits, and **ingested data is additive** — nothing needs deleting.

1. **Stop using Fyers as a price source** — in `ingest_prices.py`, drop `"fyers"` from the fallback tuple:

```python
("fyers", "yahoo_finance", "nse_india_api", "jugaad_data",
 "nsemine_history", "pnsea"),
```

becomes

```python
("yahoo_finance", "nse_india_api", "jugaad_data",
 "nsemine_history", "pnsea"),
```

2. **Stop the daily step** — in `daily_update.py`, comment out the first pipeline line:

```python
# results["fyers"] = _safe("fyers", _fyers)
```

Then `sudo systemctl restart nse-terminal` on the VM. Rows already in `prices_daily` stay (they are valid exchange bars), `fyers_*` tables simply stop growing, and `git checkout -- ingest_prices.py daily_update.py` restores the wiring. The token file can be deleted with `python fyers_client.py clear`.

## 10. Limitations and next steps

- **Daily token renewal is a manual chore.** There is no refresh loop: tokens die at ~06:00 IST, so someone must run `login-url` + `exchange` each trading day; until then the pipeline silently uses the free fallbacks. Automating it needs a headless browser or a non-interactive login policy — deliberately out of scope.
- **No fundamentals, delivery%, FII/DII or corporate-action calendar** (§1). Those stay owned by the TradingView / ScanX / bhavcopy / filings pipelines; the seam check is the price-basis consequence of not having a corporate-action calendar.
- **Screener entitlement is unproven.** `python fyers_client.py screeners` is a probe; an error envelope means "not entitled", so no screener work should be planned.
- **Index history unlocks analytics.** `INDEX_MAP` already maps `NIFTY50`, `NIFTYBANK`, `NIFTY500`, `NIFTYMIDCAP100`, `NIFTYSMLCAP100` to `NSE:...-INDEX`, so index history enables proper beta, market-breadth denominators and an `rs_rating` baseline from the exchange feed instead of a scraped proxy. Highest-value follow-up.
- **Coverage is effectively complete for NSE cash:** 1,347 of 1,349 universe symbols resolve (1,293 exact, 54 normalized); only `HEG` (renamed `HEGAM` in the exchange master) and `SSFLPP.E1` remain unresolved. Renaming `HEG` in the stock table is the cheap fix; `SSFLPP.E1` looks like an odd/placeholder series and should be checked against the master before any change.
- **Quotes are snapshots, not a tick store.** `fyers_quotes` is an audit trail keyed by `(symbol, ts)` at minute granularity — do not use it as intraday history.
