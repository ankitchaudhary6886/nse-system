# Independent verification — auth gate removal & credential residue

**Verifier:** `auth-verifier` (independent; did not author `.agents/auth-removal-report.md`)
**Date:** 2026-10-07
**Repo:** `C:\Users\Ankit\Desktop\nse_system` @ `63b60e96f4fad52f11de7eafe323dd2a45908d8b` (`main`)
**Remote:** `https://github.com/ankitchaudhary6886/nse-system.git` (PRIVATE) — `origin/main` == `63b60e9`
**Method posture:** adversarial. Every claim re-derived from the running app and from git, not from the existing report.
**Server used for live probes:** `uvicorn terminal_api:app --host 127.0.0.1 --port 8023` (started and stopped by the verifier).

---

## 1. Verdict

| # | Claim | Verdict |
|---|---|---|
| 1 | No HTTP Basic gate remains on any route (`/`, `/glossary`, `/docs`, `/redoc`, `/openapi.json`, `/static/*`, every `/api/*`) | **PASS** — 0×401 and 0×403 across 67 live probes |
| 2 | `REDACTED-PW` and `REDACTED-DEFAULT-PW` appear in **ZERO tracked files** | **PASS** (working tree) — but **FAIL in git history**, see §6 |
| 3 | `ankit` as a credential default is gone from any auth path | **PASS** — no auth path exists; only prose/path-string occurrences remain |
| 4 | No route declares an auth dependency; no `WWW-Authenticate` is ever sent | **PASS** — 0 `Depends` in executable source; 0 `WWW-Authenticate` headers observed |
| — | No other secret present | **FAIL** — a live Telegram bot token is tracked and committed, see §7 |

**Bottom line:** the gate really is gone and credentials are genuinely *ignored* (not merely optional). The defect is **residue**, not a live gate: the owner's real password `REDACTED-PW` is permanently readable in the git history that has been pushed to GitHub, and a **live Telegram bot token is committed as a tracked file right now.**

---

## 2. Route enumeration — method

Not a grep. Enumerated the real route table from the running process:

```powershell
$j = (Invoke-WebRequest "http://127.0.0.1:8023/openapi.json" -UseBasicParsing).Content | ConvertFrom-Json
```

`openapi.json` returned:

- `info.title` = `NSE Intelligence Terminal`, `info.version` = `24.1`
- **65 paths / 67 operations** (GET 53, POST 13, DELETE 1)
- `components.securitySchemes` → **absent**
- top-level `security` → **absent**

### 2a. Every no-parameter route, NO `Authorization` header (34 routes)

```
path                     status   seconds
/                        200      0.136
/glossary                200      0.016
/api/compare             422      0.012   <- missing required ?symbols= (validation, not auth)
/api/deployment-check    200      0.670
/api/explain             200      0.016
/api/health              200      0.115
/api/ideals              200      0.020
/api/league/overview     200      0.114
/api/league/status       200      0.280
/api/ledger/stats        200      0.024
/api/ledger/trades       200      0.017
/api/macro               200      0.019
/api/model/runs          200      0.023
/api/patterns/latest     200      0.084
/api/patterns/stats      200      0.032
/api/positional          200      0.046
/api/radar               200      5.462
/api/regime              200      1.294
/api/research-sector     200      3.424
/api/research-universe   200      1.152
/api/screener/scan       200      3.475
/api/sources             200      0.029
/api/strategies          200      0.014
/api/strategy-runs       200      0.019
/api/strategy-summary    200      0.018
/api/swing/scan/status   200      0.008
/api/swing/signals       200      0.032
/api/templates/latest    200      0.019
/api/toppicks            200      8.933
/api/trend               200      0.030
/api/validate/latest     200      0.024
/api/value-radar         200      0.023
/api/delivery/top        200      0.024
/api/delivery/accum      200      0.021
SUMMARY: HTTP 200 : 33   HTTP 422 : 1   AUTH_FAILS (401/403) : 0
```

### 2b. Parameterized routes, built-ins, static — no credentials (25 probes)

```
GET /api/cockpit/RELIANCE/chart          200
GET /api/cockpit/RELIANCE/summary        200
GET /api/compare?symbols=RELIANCE,TCS    200
GET /api/delivery/RELIANCE               200
GET /api/explain/RSI                     200
GET /api/ideals/p_win                    200
GET /api/league/player/nonexistent-slug-xyz  200
GET /api/meta/RELIANCE                   200
GET /api/patterns/RELIANCE               200
GET /api/patterns/history/RELIANCE       200
GET /api/research/RELIANCE               200
GET /api/screener/RELIANCE               200
GET /api/sizing/RELIANCE                 200
GET /api/strategies/nonexistent-strategy-xyz  404  (not found, not 401)
GET /api/traders/matches/RELIANCE        200
GET /api/traders/nonexistent-slug-xyz    404  (not found, not 401)
GET /docs                                200
GET /redoc                               200
GET /openapi.json                        200
GET /static/index.html                   200
GET /static/app.js                       200
GET /static/nope-does-not-exist.js       404
GET /api/does-not-exist                  404
SUMMARY: HTTP 200 : 21   HTTP 404 : 4   AUTH_FAILS : 0
```

### 2c. POST / DELETE without credentials

```
POST   /api/sizing/capital  {"capital":-5}                 -> 400  (app validation: capital must be > 0)
DELETE /api/strategies/nonexistent-strategy-xyz            -> 200  (silent no-op)
POST   /api/webhook/ingest  {}                             -> 503  (webhook not configured; app-level token, not the gate)
```

**No 401 or 403 was produced by any route in the app.** The only authentication left anywhere is the unrelated `POST /api/webhook/ingest` shared-secret check (`terminal_api.py:877-893`), which is a webhook token — not the HTTP Basic login gate — and it did not fire the Basic challenge.

**Not exercised deliberately:** the 9 mutating background-job POSTs (`/api/swing/scan`, `/api/trend/scan`, `/api/pwn/refresh`, `/api/patterns/scan`, `/api/strategies/seed`, `/api/strategies/run-all`, `/api/league/replay`, `/api/league/simulate`, `/api/research-cache/clear`). They were skipped to avoid kicking off real scans on the owner's machine. They are covered by the static proof in §5 (zero `Depends` in `terminal_api.py`) and by the absent `security`/`securitySchemes` in `openapi.json`. **This is a known residual gap in my coverage and is disclosed rather than glossed.**

---

## 3. Claim 4 — no challenge is ever sent

```
----- GET / -----
HTTP/1.1 200 OK
date: Wed, 07 Oct 2026 17:15:07 GMT
server: uvicorn
content-type: text/html; charset=utf-8
accept-ranges: bytes
content-length: 44265
last-modified: Wed, 07 Oct 2026 14:33:03 GMT
etag: "dc0079bc52198248ab3b050e9b09dd58"

----- GET /api/health -----
HTTP/1.1 200 OK
date: Wed, 07 Oct 2026 17:15:07 GMT
server: uvicorn
content-length: 69
content-type: application/json

----- GET /glossary ----- 200, content-type text/html; charset=utf-8
----- GET /docs -----     200, content-type text/html; charset=utf-8
----- GET /openapi.json - 200, content-type application/json
----- GET /api/sources -- 200, content-type application/json
```

`WWW-Authenticate` present in `/` headers: **False**
`WWW-Authenticate` present in `/api/health` headers: **False**

**PASS.**

---

## 4. Claim 1/3 — credentials are IGNORED, not merely optional

24 combinations of deliberately wrong / real credentials against 6 routes, plus a POST and a DELETE:

```
credential                       route            status
wronguser:wrongpass              /                200
wronguser:wrongpass              /api/health      200
wronguser:wrongpass              /api/sources     200
wronguser:wrongpass              /api/strategies  200
wronguser:wrongpass              /glossary        200
wronguser:wrongpass              /openapi.json    200
ankit:deliberately-wrong-password  (all 6 routes)  200
ankit:REDACTED-PW                     (all 6 routes)  200
ADMIN:REDACTED-DEFAULT-PW         (all 6 routes)  200

POST   /api/sizing/capital   with wronguser:wrongpass  -> 400 (validation only)
DELETE /api/strategies/nonexistent-strategy-xyz with wronguser:wrongpass -> 200
```

Every one of the 24 returned **200**. Sending the owner's *real* credential produced exactly the same result as sending garbage: the credential is not read at all. No response body echoed the credential back (`/api/health` body contained no `ankit`). **PASS.**

---

## 5. Claim 3/4 — static proof

**Exact command:**

```powershell
git grep -n -I -e "Depends" -e "HTTPBasic" -e "WWW-Authenticate" -e "APP_PASS" -e "APP_USER" -e "compare_digest" -- 2>$null
```

**Raw output (21 `Depends` hits + 18 gate-artifact hits), grouped:**

| Where | Nature | Live auth path? |
|---|---|---|
| `.agents/auth-removal-report.md` (15 `Depends`, 7 `HTTPBasic`, 2 `WWW-Authenticate`, all `APP_USER`/`APP_PASS`) | the previous agent's own report, quoting the deleted code | No — prose |
| `.agents/MEMORY.md:168`, `.agents/SUBAGENTS.md:188` | stale rule text telling future agents to add `Depends(verify_user)` | No — prose |
| `.agents/cache/FINDINGS.md:129,134,137,454`, `.agents/cache/JOIN_HERE.md:148` | stale findings text | No — prose |
| `glossary_ui.py:16` | **stale module docstring**: `def glossary(user: str = Depends(verify_user)):` | No — inside a `"""docstring"""`
| `terminal_api.py:890-891` | `secrets.compare_digest(got_hdr, token)` — **webhook token**, unrelated to the login gate | No |

- `terminal_api.py`: **0 hits** for `HTTPBasic`, `WWW-Authenticate`, `verify_user`, `APP_USER`, `APP_PASS`, `Depends`, `security`. The import line (`terminal_api.py:9`) is `from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Header, Query` — **`Depends` and `HTTPBasic` are absent**.
- The only `401` left in `terminal_api.py` is line **893**, the webhook token rejection. All other `HTTPException`s are 400/404/422/500/503.
- Quoted literal `"ankit"` as a credential default survives in exactly one tracked file: `.agents/auth-removal-report.md:44`, inside a quoted code block. Not a live auth path.
- `main.py`, `app.py` (Streamlit), `config.py`, `db.py`: **0 gate artifacts**. `terminal_api.py` is the only FastAPI server in the repo (`terminal/terminal_api.py` no longer exists).

The `Depends\s*\(` form I first tried returned 0 hits — a **false negative**, because git's POSIX ERE has no `\s`. Re-run without it, as above. Flagging this so the finding is not mistaken for a real zero.

### `ankit` occurrences that are NOT credentials (confirmed)

- Windows path `C:\Users\Ankit\Desktop\nse_system` / `C:\Users\Ankit\.ssh\nse.pem` — in `.agents/AGENT_SETUP.md`, `.agents/MEMORY.md`, `PROJECT_HANDOFF.md`, `deploy.bat`, `daily_update.bat`, `.github/hooks/ctx-gate.json`, `.vscode/settings.json`, `.agents/mcp_config.json`, `.agents/memory.py`, `.agents/skills/*`, `tools/ui-audit/README.md`.
- GitHub username `ankitchaudhary6886` — `PROJECT_HANDOFF.md:35`, `terminal/static/index.html:648-652`.
- Owner-name prose (`Ankit's NSE system`, `Owner vision — Ankit`) — `.agents/MEMORY.md:1`, `backlog.md:1`, `PORTAL_REDESIGN.md:4`, `PROJECT_HANDOFF.md:10`.

**None of these are credentials.** Confirmed.

---

## 6. GIT HISTORY — THE HEADLINE FINDING

`git grep` over the working tree is clean. **Git history is not.**

### 6.1 `REDACTED-PW` (the owner's real password) — RECOVERABLE VERBATIM

**All four commits below are reachable from `origin/main`** (`git merge-base --is-ancestor <sha> HEAD` → true for each):

| Commit | Date | File:line | Recovered text |
|---|---|---|---|
| `3aae9419ecd88a6a0211e8d7268038f4a509d3cf` | 2026-09-07 | `PROJECT_HANDOFF.md:33` | `- Login: ADMIN_USER=ankit, ADMIN_PASS=REDACTED-PW (stored in ~/nse-system/.env on VM; change anytime)` |
| `c0ba7be6ce14c500fb17a5b2dbafea8b0b61f7d2` | 2026-09-12 | `PROJECT_HANDOFF.md:34` | same login line |
| `c0ba7be6ce14c500fb17a5b2dbafea8b0b61f7d2` | 2026-09-12 | `verify_deployment.py:139` | `auth=("ankit", "REDACTED-PW"), timeout=5)` |
| `ceb4d5a7da09081c7664dcecdc085cd8b1ef2605` | 2026-09-26 | `PROJECT_HANDOFF.md:38`, `verify_deployment.py:166` | same login line / same `auth=` line (**not** reachable from HEAD; dangling ref, still in `.git`) |
| `3057927d34d8fe73629767c7581144641a1a789b` | 2026-10-05 | `PROJECT_HANDOFF.md:38`, `verify_deployment.py:166`, `.agents/AGENT_SETUP.md:161`, `.agents/MEMORY.md:184`, `.agents/cache/FINDINGS.md:257`, `.agents/cache/JOIN_HERE.md:187` | same credential, now also quoted in agent docs |

**Removed by** `63b60e96f4fad52f11de7eafe323dd2a45908d8b` (2026-10-07, `HEAD`) — the working tree is clean, the history is not.

**Proof of readability (run by the verifier):**

```powershell
git show 3aae9419:PROJECT_HANDOFF.md | Select-String "ADMIN_PASS"
# -> - Login: ADMIN_USER=ankit, ADMIN_PASS=REDACTED-PW (stored in ~/nse-system/.env on VM; change anytime)

git show c0ba7be6:verify_deployment.py | Select-String "auth="
# -> auth=("ankit", "REDACTED-PW"), timeout=5)
```

**Exposure surface:** `origin/main` == `HEAD` == `63b60e9` and the remote is `github.com/ankitchaudhary6886/nse-system.git`. The secret has been **pushed**. It is therefore in (a) the GitHub private repo's history, (b) the VM clone `~/nse-system` history, and (c) every developer clone. A private repo is not a secret store.

### 6.2 `REDACTED-DEFAULT-PW` (the in-code default) — RECOVERABLE

| Commit | Date | File:line |
|---|---|---|
| `602a2674e62126f45ec8ab2e3de6934d11df9b0a` | 2026-08-30 | `terminal/terminal_api.py` — `APP_PASS = os.getenv("ADMIN_PASS", "REDACTED-DEFAULT-PW")` |
| `3057927d34d8fe73629767c7581144641a1a789b` | 2026-10-05 | `terminal_api.py:19`, `.agents/cache/env_index.json:181` |

Both reachable from `HEAD`; removed by `63b60e96`.

```powershell
git show 602a2674:terminal/terminal_api.py | Select-String "APP_PASS"
# -> APP_PASS = os.getenv("ADMIN_PASS", "REDACTED-DEFAULT-PW")
```

### 6.3 The git-history commands used

```powershell
git log HEAD --format="%H|%ad|%s" --date=short -S "REDACTED-PW"
git log HEAD --format="%H|%ad|%s" --date=short -S "REDACTED-DEFAULT-PW"
git log --all  --format="%H|%ad|%s" --date=short -S "REDACTED-PW"
git grep -n -i -e "REDACTED-PW" -e "REDACTED-DEFAULT-PW" <sha>
```

**No history rewrite was attempted**, per instruction. Rewriting `main` after a push would not remove the objects from GitHub anyway (needs a GitHub-side purge / support request).

---

## 7. ADDITIONAL SECRET — live Telegram bot token, TRACKED and COMMITTED

**Not one of the two named strings, therefore outside the stated scope — found by scanning for hardcoded credential sources.**

```
data/tg_secret.txt:1   len=46   redacted=86503310...-jx8   matches bot-token pattern ^\d{8,12}:[A-Za-z0-9_-]{30,}$  = True
data/tg_secret.txt:2   len=10   (chat id, short)
```

- **Tracked at HEAD:** `git ls-files --error-unmatch data/tg_secret.txt` → exit 0.
- **Committed:** `git rev-list HEAD -- data/tg_secret.txt` → `2580d84b2f57b9edbfe4a869e91e876eda58c986` ("NSE system 2.0"), which **is reachable from HEAD** and therefore pushed to `origin/main`. Also present in the dangling checkpoint `ceb4d5a7`.
- **Working tree is identical to the committed blob** (`git diff --stat HEAD -- data/tg_secret.txt` empty) — i.e. the tracked content is the live token, and `alerts.py:22` / `alerts.py:_creds()` reads exactly this file.
- **Not covered by `.gitignore`.** `.gitignore` lists `data/*.db`, `data/gcp_key.json`, `data/daily_log.txt`, `data/uploaded_fundamentals.csv`, `data/charts/`, `data/incoming/` — but **not** `data/tg_secret.txt`.

Recovery proof (redacted here; the full value is trivially readable):

```powershell
git show 2580d84:data/tg_secret.txt   # -> 86503310...-jx8 (46 chars)
```

**Not scrubbed, per instruction.** Anyone with read access to the private repo can send Telegram messages as the owner's bot.

### Other secrets checked

- Hardcoded credential assignments with a non-empty literal default in tracked `*.py/*.js/*.mjs/*.json/*.yml/*.yaml/*.toml/*.cfg/*.ini/*.service/*.env*`: **zero hits** (`git grep -E "(password|passwd|secret|token|api_key)[A-Za-z_]*\s*[:=]\s*['\"][^'\"]{3,}['\"]"` → exit 1).
- `getenv` with a non-empty literal default in tracked `.py/.js/.mjs` — only two, both benign:
  - `terminal_api.py:17`: `API_HOST = os.getenv("API_HOST", "127.0.0.1")`
  - `verify_deployment.py:165`: `api_base = os.getenv("API_BASE", "http://127.0.0.1:8000")`
- `data/gcp_key.json` is gitignored and **absent** from the index (`git ls-files --error-unmatch` → did not match). No leak.
- `TELEGRAM_TOKEN`, `WEBHOOK_TOKEN`, `ALPHA_VANTAGE_API_KEY` all read from env with **empty/absent** defaults.
- `verify_deployment.py` at HEAD now calls `/api/health` **with no `auth=`** — the F-16 hardcoding is genuinely fixed in the working tree.

---

## 8. Residual (non-credential) artifacts of the removed gate

Reported for completeness; none is a usable credential.

| Artifact | Detail | Tracked? |
|---|---|---|
| `.codegraph/codegraph.db` | The local code-graph index still contains the literal `REDACTED-DEFAULT-PW` and the old `APP_USER = os.getenv("ADMIN_USER", "ankit")` / `security = HTTPBasic()` nodes. Does **not** contain `REDACTED-PW`. | No — gitignored (`.gitignore`: `.codegraph/`) |
| `__pycache__/glossary_ui.cpython-314.pyc` | Stale bytecode containing the docstring string `verify_user`. | No — gitignored (`__pycache__/`, `*.pyc`) |
| `glossary_ui.py:16` | Stale module **docstring** showing `def glossary(user: str = Depends(verify_user)):`. Copy-paste hazard for a future agent, not a live dependency. | **Yes** |
| `.agents/MEMORY.md:168`, `.agents/SUBAGENTS.md:188` | Rule text "every new route needs `Depends(verify_user)`" now describes a dependency that does not exist. | **Yes** |
| `to do list.txt:7` | `⬜ S4 .env with real ADMIN_USER / ADMIN_PASS for terminal_api [HUMAN]` — stale TODO for a gate that no longer exists. | **Yes** |
| `PROJECT_HANDOFF.md:36` | Still reads `Modern terminal: http://140.238.226.249:8000 (FastAPI, HTTP Basic login)` while line 38 says login is disabled. Self-contradictory doc. | **Yes** |
| `PROJECT_HANDOFF.md:261` | Future plan still says nginx reverse proxy should `(keep Basic auth)`. Moot. | **Yes** |
| `tools/ui-audit/*.mjs` | 12 references to `process.env.ADMIN_USER` / `ADMIN_PASS`; the tooling supports an optional gate and correctly defaults to no credentials. `probe.mjs:196` explicitly states "this repo's terminal_api.py has no login gate". | **Yes** |

---

## 9. Deployment surface — factual

- **Served by:** `nse-terminal.service` on the VM — `uvicorn terminal_api:app --host 0.0.0.0 --port 8000`, `Environment=PYTHONUNBUFFERED=1` (`PROJECT_HANDOFF.md:42-43`). The `.service` file is **not in this repo**; it lives on the VM.
- **In-repo default bind:** `terminal_api.py:17` `API_HOST = os.getenv("API_HOST", "127.0.0.1")` and `terminal_api.py:1104` `uvicorn.run(..., host=API_HOST, port=8000, reload=True)`. The **default is loopback**; production overrides it to `0.0.0.0` on the command line.
- **Public address:** `http://140.238.226.249:8000` (`PROJECT_HANDOFF.md:36`).
- **Firewall:** `PROJECT_HANDOFF.md:41` — "Open ports (Oracle security list + iptables): TCP 8501, 8000 from `0.0.0.0/0`."
- **Legacy second surface:** `nse.service` (Streamlit) on `:8501`, also open to `0.0.0.0/0`. Streamlit (`app.py`) has no gate either.
- A second FastAPI server in `terminal/` no longer exists (`Test-Path terminal\terminal_api.py` → `False`).

**Consequence of removing the gate, stated factually:** before removal, an anonymous request from the public internet to `140.238.226.249:8000` received `401` + `WWW-Authenticate`. After removal, **all 67 operations are anonymously reachable from `0.0.0.0/0`**, including the 13 POSTs and 1 DELETE. Those include endpoints that trigger scans and backtests, write strategy definitions (`POST /api/strategies/{name}`), delete strategy definitions (`DELETE /api/strategies/{name}`), and — via the app's own Telegram integration — can cause messages to be sent to the owner's Telegram. `GET /openapi.json`, `/docs` and `/redoc` are also now anonymously readable, exposing the full API surface. No editorialising beyond this: the gate removal is exactly what the owner asked for; this is what it changes.

---

## 10. What the owner must still do

1. **ROTATE the password `REDACTED-PW`.** It cannot be un-published from git history. Since it was the owner's real login (and per `3aae9419:PROJECT_HANDOFF.md:33` it was also stored in `~/nse-system/.env` on the VM), treat it as compromised **everywhere it was reused** — GitHub, SSH, email, anywhere. Changing it in the repo does nothing; the old value stays in history.
2. **ROTATE the Telegram bot token.** `data/tg_secret.txt:1` is tracked, committed (`2580d84`), pushed to GitHub, and read live by `alerts.py:22`. Revoke it via `@BotFather` (`/revoke`) and issue a new one. This is the only *currently live* credential in the working tree.
3. **Untrack `data/tg_secret.txt` and move it out of the repo.** `git rm --cached data/tg_secret.txt`, add `data/tg_secret.txt` to `.gitignore`, and keep the real token in an env var or outside the tree. Note: this does **not** remove it from history.
4. **Decide on the VM `~/nse-system/.env`.** `PROJECT_HANDOFF.md` (historical) documented `ADMIN_USER=ankit`, `ADMIN_PASS=REDACTED-PW` there. `terminal_api.py` no longer reads either variable, so they are inert for this app — but the file may still exist on the VM with a live, reused password in plaintext.
5. **Decide on git-history purge (optional).** If the private repo's history must be cleaned, that requires `git filter-repo` **plus** a GitHub-side purge (force-push is not sufficient — old objects remain fetchable by SHA and in forks/clones). Confirm no other clone or fork exists first.
6. **Clean the stale auth references** listed in §8 (`glossary_ui.py:16` docstring, `.agents/MEMORY.md:168`, `.agents/SUBAGENTS.md:188`, `to do list.txt:7`, and the self-contradictory `PROJECT_HANDOFF.md:36` / `:261`) so a future agent does not re-add a gate on the strength of stale instructions.
7. **Accept or reverse the public exposure** of §9. If the terminal is meant to stay on the open internet, that is now an unauthenticated control surface; if not, restore a gate (the owner's instruction was to remove it, so this is a decision to surface, not to make unilaterally).

---

## 11. Reproduce

```powershell
cd C:\Users\Ankit\Desktop\nse_system
# 1. route truth
& env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8023
curl.exe -s http://127.0.0.1:8023/openapi.json
curl.exe -s -D - -o NUL http://127.0.0.1:8023/            # expect 200, NO WWW-Authenticate
curl.exe -s -o NUL -w "%{http_code}" -u wrong:wrong http://127.0.0.1:8023/api/health   # expect 200
# 2. working tree clean of both strings (expect no hits)
git grep -n -i -e "REDACTED-PW" -e "REDACTED-DEFAULT-PW"
# 3. history is NOT clean (expect hits)
git log HEAD --format="%H|%ad|%s" --date=short -S "REDACTED-PW"
git log HEAD --format="%H|%ad|%s" --date=short -S "REDACTED-DEFAULT-PW"
git show 3aae9419:PROJECT_HANDOFF.md | Select-String "ADMIN_PASS"
git show c0ba7be6:verify_deployment.py | Select-String "auth="
# 4. tracked live secret
git ls-files --error-unmatch data/tg_secret.txt
git show 2580d84:data/tg_secret.txt
```

**Verdict on the owner's requirement:** the username and password are gone from the *site* and from the *working tree* — the login gate is genuinely, verifiably removed and credentials are ignored. They are **not** gone from the repository's history, and a different live credential (Telegram bot token) is committed right now.
