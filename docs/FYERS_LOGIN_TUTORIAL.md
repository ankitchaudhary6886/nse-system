# Fyers Daily Login — Beginner Walkthrough

Read this once end-to-end, then use §8 as your daily cheat sheet. It complements [FYERS_INTEGRATION.md](FYERS_INTEGRATION.md) (the full runbook: architecture, ingestion guards, VM rollout) — it does not repeat it. App ID: `2DA83NVOJU-100`. App type: **Non-trading** (read-only market data, no orders).

## 1. What this login actually is

Fyers gives a program access to market data only through **OAuth**: your browser logs in as *you*, you approve the app once, Fyers hands back a short **auth code**, and that code is swapped for an **access token**. The token is what the scripts actually use. Nothing here can place, modify or cancel an order — the app is registered Non-trading and no order endpoint is ever called.

That token is deliberately short-lived: Fyers kills it around **06:00 IST** the next day, so the login must be repeated once per trading day. It cannot be automated for free because a human must type the Fyers password and the **OTP that arrives on your phone** — no free API issues a token without that consent. Automating it would mean storing your password in a script and still needing the phone OTP, so this project keeps it manual and honest.

```
You (laptop browser)                Fyers                        This project
--------------------                -----                        ------------
1. python fyers_client.py login-url
                                    <-- prints one long URL
2. open that URL, log in, enter OTP
3. approve the app            ---->  creates an auth_code
   redirect: https://fyers.in/?auth_code=<CODE>&state=nse_system
4. copy the auth_code (or whole URL) from the address bar
5. python fyers_client.py exchange --code '<CODE>'
                                    <-- validate-authcode (appIdHash + code)
                                    --> returns access_token
                                                                 stores data/fyers_token.json
6. python ingest_fyers.py status    --> "token_valid": true
   valid until 05:55 IST tomorrow (broker dies ~06:00)
```

Plain glosses: **OAuth** = "log in with Fyers yourself, app gets a limited pass". **auth_code** = a one-time ticket, worthless after one use or a few minutes. **access_token** = the day-pass that the data scripts send on every request. **appIdHash** = a fingerprint built from App ID + Secret ID; it is how Fyers knows the app asking is really yours.

## 2. Before you start (one-time setup, do this today, never again)

1. **Fyers account** — an active Fyers trading account, and your phone can receive the OTP. The account you log in with must be the account that owns the API app.
2. **API dashboard** — log in at `myapi.fyers.in` and confirm:
   - the app exists and its **App ID** is `2DA83NVOJU-100`;
   - **App type** is `Non-trading`;
   - **Secret ID** is visible (you will copy it, never retype it);
   - **Redirect URI** is exactly `https://fyers.in` — no trailing slash, no `/callback`. One wrong character here breaks login with a redirect error.
3. **`.env` file** — lives at the project root, `C:\Users\Ankit\Desktop\nse_system\.env`, and holds:

```text
FYERS_APP_ID=2DA83NVOJU-100
FYERS_SECRET_ID=<the secret from the dashboard>
FYERS_REDIRECT_URI=https://fyers.in
```

4. **Verify `.env` without printing the secret.** PowerShell has no `grep`, so use these:

```powershell
cd C:\Users\Ankit\Desktop\nse_system
Select-String -Path .env -Pattern '^FYERS_APP_ID=' | ForEach-Object { $_.Line }
(Select-String -Path .env -Pattern '^FYERS_').Count
```

Expected: `FYERS_APP_ID=2DA83NVOJU-100` then `3`. (In Git Bash or on the VM the same check is `grep '^FYERS_APP_ID=' .env` and `grep -c '^FYERS_' .env` — identical result.) If the count is `2`, a key is missing; if `0`, the file is missing or named `.env.txt`.

5. **If `.env` is missing**, create it from the project folder (this opens an empty editor named exactly `.env`), paste the three lines above, replace the secret placeholder in the editor, save, close:

```powershell
cd C:\Users\Ankit\Desktop\nse_system
notepad .env
```

`.env` is already gitignored, so it can never be committed. Never paste the secret into chat, Telegram, or a screenshot you keep.

## 3. The daily login, step by step

Do these in order, in **one** PowerShell window. Each step: type this → should see this → if not → why.

### Step 1 — open a terminal in the project

```powershell
cd C:\Users\Ankit\Desktop\nse_system
Get-Location
```

Should see: `Path` line ends with `C:\Users\Ankit\Desktop\nse_system`.
If not: "Cannot find path" means the folder was moved or renamed — find it in File Explorer, then `cd` to its real path.
Why: every command below (`fyers_client.py`, `.env`, `data\`) is found relative to this folder.

### Step 2 — activate the virtual environment

```powershell
.\env\Scripts\Activate.ps1
```

Should see: your prompt now starts with `(env)`.
If you see `... cannot be loaded because running scripts is disabled`: run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then `.\env\Scripts\Activate.ps1` again. If it still refuses, skip activation entirely and replace `python` with `.\env\Scripts\python.exe` in every command below — that works and needs no activation.
Why: the venv holds the `requests` library the client needs. Wrong Python = `ModuleNotFoundError: requests`.

### Step 3 — ask the client for the login URL

```powershell
python fyers_client.py login-url
```

Should see (one long URL, then a hint line):

```text
https://api-t1.fyers.in/api/v3/generate-authcode?client_id=2DA83NVOJU-100&redirect_uri=https%3A%2F%2Ffyers.in&response_type=code&state=nse_system

Open the URL, approve the app, then copy the auth_code parameter from the redirected URL.
```

If you see `FYERS_APP_ID is not configured (.env)`: `.env` is missing, misnamed, or has a typo in the key name — go back to §2 step 4.
Why: this URL carries your App ID, the redirect URI and a `state` marker; it is the "ask permission" page, not a login by itself.

### Step 4 — open that URL on **this laptop's** browser and approve

Copy the URL and paste it into a browser **on this laptop** — not your phone. Log in with the Fyers account, enter the OTP from your phone, and approve the app.
If the page seems to hang after approving, wait a second; it will jump to `https://fyers.in/...` and may look blank or like the Fyers home page.
Why the laptop: the auth code is **single-use and short-lived**, and it has to reach this machine's terminal. Moving a long code from phone to laptop costs minutes and mistakes; the token is also stored on this laptop, so a phone login would help nothing.

### Step 5 — copy the `auth_code` from the address bar

The address bar now looks like `https://fyers.in/?auth_code=eyJhb...&state=nse_system`. Select from just after `auth_code=` up to the `&` before `state=`, and copy — **or** copy the whole URL, the client accepts both and extracts the code itself.
If the page is blank or shows an error: copy from the URL anyway. The code is in the address bar even when the page renders nothing.
Why: the app never sees your Fyers password or OTP; the code in the URL is the only proof of your approval.

### Step 6 — exchange the code for today's token (do this immediately)

Paste your code where `<PASTE_AUTH_CODE>` is. Keep the **single quotes**: PowerShell treats them as literal text, so a whole pasted URL with `?` and `&` is safe inside them.

```powershell
python fyers_client.py exchange --code '<PASTE_AUTH_CODE>'
```

Should see exactly two lines:

```text
token stored: 2026-10-19T05:55:00+05:30 IST
profile: <your Fyers display name>
```

- `token stored:` = the expiry this project will honour (05:55 IST, five minutes before the broker's ~06:00 cut-off).
- `profile:` = proof of life: the client just called Fyers with the new token and got your account name back.

If instead you see `token exchange FAILED: ...` — stop, read §5 (`-437` and the O/0 app-hash row are almost always the cause), and redo steps 3–6 with a **fresh** code.
If you forget `--code`, the client asks `Paste the auth_code (or the full redirect URL):` — paste and press Enter (Ctrl+V, not Ctrl+C, to paste in PowerShell).

### Step 7 — confirm the token is live

```powershell
python ingest_fyers.py status
```

Should see a JSON block containing `"present": true` and, near the bottom:

```json
  "token_valid": true
```

If `"token_valid": false`, the file exists but Fyers rejects the token (§5). Why this step: `token_valid` is the only field that proves the token works **right now** — `present: true` only means a file exists.

## 4. How to know it worked / how to know it expired

Read these four fields, in this order, from `python ingest_fyers.py status`:

| Field | Working | Meaning in plain English |
|---|---|---|
| `credentials.token.token_file` | `...\data\fyers_token.json` | Where the day-pass is stored on this laptop |
| `credentials.token.present` | `true` | A token exists on disk (it can still be stale) |
| `credentials.token.expires_at` | `2026-10-19T05:55:00+05:30` | The moment this project stops trusting it |
| `token_valid` | `true` | Fyers accepted the token just now — the only real proof |

`python fyers_client.py status` is the short human version: `credentials: app_id=2DA83NVOJU-100 secret=set redirect=https://fyers.in`, then the token JSON, then `profile: ok — <name>` and a `marketStatus:` line.

**Expired looks like this** — same JSON with two values changed, plus a warning line from `fyers_client.py status`:

```text
WARNING: stored token is past its expiry; re-run login.
"expires_at": "2026-10-18T05:55:00+05:30", "expired": true, "token_valid": false
```

No token at all looks different: `"present": false`, `"expired": null`, `token_valid: false`, and the client prints `No token. Run: python fyers_client.py login-url` (exit code `1`). Both cases have the same fix: repeat §3.

The token lives in `data\fyers_token.json` (gitignored by the `data/*token*` rule) and holds `access_token`, `refresh_token`, `issued_at`, `expires_at`, `profile`. **Never paste its contents anywhere** — not in chat, not in a bug report, not in Telegram. Anyone holding that string can pull data as you until 06:00. You never need to read it; the commands read it for you.

## 5. Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| `token exchange FAILED: ... (code=-437)` | Auth code rejected: already used, or too much time passed. Codes are **single-use** | Redo §3 steps 3–6. Copy the new code and run `exchange` immediately, no detours |
| `code=-16` / `-17`, or `AUTH FAILED: ... (HTTP 401)` | The token is invalid: a second login elsewhere, a password change, or a stale file | `python fyers_client.py clear`, then log in again (§3) |
| App-hash / invalid-app-credentials error although the code is brand new | `FYERS_SECRET_ID` is wrong — it was originally transcribed from a screenshot, where letter **O** and digit **0** are identical. The two characters after `HDIT` are the doubt: they can be **two letter O's**, or **letter O followed by digit zero**, then `853C` (the exact value is deliberately not written in this repo) | Copy-paste the secret from `myapi.fyers.in`, never retype; try the other reading of those two characters; save `.env`; run `exchange` with a **fresh** code |
| Redirect / `redirect_uri` mismatch page | App's Redirect URI ≠ `FYERS_REDIRECT_URI` | Make both exactly `https://fyers.in` (dashboard and `.env`), no slash, save, redo §3 |
| `ingest_fyers.py status` shows `token_valid: false` | No token, or an expired/rejected token | Run `python fyers_client.py status` to see which; then §3 |
| Daily log line `FYERS SKIPPED: {'ok': false, 'skipped': 'no fyers token'}` | The pipeline ran before you logged in today. Not an outage — free sources carried on | Do the login when convenient, then re-run `python ingest_fyers.py sync` |
| `broker rate limit hit (code=-429)` | Too many requests: another script using the same app, or a retry storm. Our client already caps at 8 req/s and 180 req/min | Wait ~60 seconds and retry once. Never run two Fyers ingests at the same time |
| Browser shows a blank `fyers.in` page after approving | Normal — that page has nothing to render for an app redirect | Copy the `auth_code` from the **address bar** anyway and continue to `exchange` |
| Login succeeded but `profile:` shows a name that is not yours | You are logged into a different Fyers account in that browser | Log out of Fyers in the browser, log in with the app's owning account, redo §3 (and `python fyers_client.py clear` first) |
| Clock/timezone look wrong, or a "token issued in the future/past" style error | The expiry is computed in IST (`Asia/Kolkata`); a wrong laptop clock breaks that arithmetic | Windows Settings → Time & Language → turn on **Set time automatically**, set time zone to **India Standard Time**, reboot the terminal, log in again |
| You log in at 2 a.m. or on a Sunday and it still works | Expected — the token is about *access*, not about the market being open | Nothing. Data calls simply return the last completed session's bars |

## 6. Security and hygiene

1. **Never commit** `.env` or `data/fyers_token.json`. Both are already blocked by `.gitignore` (`env/`, `.env`, `data/*token*`). Before any commit, `git status --short` must show neither file.
2. **Never paste** the token or the secret into chat, Telegram, an issue, a log, or a screen share. A broker token is a password with an expiry date.
3. **If the token leaks**: Fyers dashboard → log out of all sessions / reset the password, then `python fyers_client.py clear` and log in again. The old token dies at the latest at 06:00, but do not wait.
4. **If the secret leaks** (for example it lands in a commit): regenerate the **Secret ID** on `myapi.fyers.in`, update `.env` on every machine, and treat the old secret as burnt. Deleting the file later does not remove it from git history.
5. **Worst case is limited by the app type.** This is a Non-trading app: no order, position, holdings or funds endpoint exists in this repo. The worst a leak allows is reading your own profile and market data — not trading your account.

## 7. Where this fits next

Login is step zero of the data setup. On the first day only, continue in this order — `master` (import the NSE symbol list) → `verify --limit 20 --days 10` (cross-check the broker against stored bars) → `history --days 30` (backfill; expect 8–10 minutes) → `rebuild_raw_history.py run --limit 10` (the pilot). The exact commands, expected output and the rebuild guardrails are in [FYERS_INTEGRATION.md §4](FYERS_INTEGRATION.md) — use that section rather than retyping from memory. After day one, the only recurring job is the login in §3, then `python ingest_fyers.py sync`.

## 8. Cheat sheet — the whole day in four commands

```powershell
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\Activate.ps1
python fyers_client.py login-url
python fyers_client.py exchange --code '<PASTE_AUTH_CODE>'
```

| # | Command | Expected result | If it fails |
|---|---|---|---|
| 1 | `python fyers_client.py login-url` | One long `...generate-authcode?...client_id=2DA83NVOJU-100...` URL + hint line | `FYERS_APP_ID is not configured` → fix `.env` (§2) |
| 2 | open URL, log in + OTP, approve, copy `auth_code` from address bar | Address bar shows `https://fyers.in/?auth_code=<CODE>&state=nse_system` | Blank page is normal — copy from the URL. Redirect error → Redirect URI ≠ `https://fyers.in` |
| 3 | `python fyers_client.py exchange --code '<PASTE_AUTH_CODE>'` | `token stored: <tomorrow>T05:55:00+05:30 IST` and `profile: <name>` | `-437` → fresh code, run immediately; app-hash error → secret O vs 0 (§5) |
| 4 | `python ingest_fyers.py status` | `"present": true`, `"expired": false`, `"token_valid": true` | `token_valid: false` → `python fyers_client.py status` to see why, then `clear` and redo 1–3. Clean slate: `python fyers_client.py clear` |
