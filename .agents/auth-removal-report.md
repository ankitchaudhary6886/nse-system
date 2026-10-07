# Auth removal — login gate deleted, credentials scrubbed

> **Note on redaction.** This report deliberately does **not** contain the two credential literals
> it removed, because the report itself lives in the repo and must not fail the "zero occurrences"
> acceptance test. They are referred to throughout as:
>
> - **`<OWNER-PASSWORD>`** — the owner's real password formerly hardcoded in `verify_deployment.py`
> - **`<DEFAULT-PASSWORD>`** — the old in-code default password formerly in `terminal_api.py`
>
> To re-verify, grep the repo (excluding `env/`, `node_modules/`, `.git/`) for the two known
> strings; both must return **0**.

- **Task:** team task `task-3` ("Auth: remove HTTP Basic login gate and scrub credentials")
- **Owner:** teammate `auth-removal`
- **Repo:** `C:\Users\Ankit\Desktop\nse_system`
- **Date:** 2026-10-07
- **Owner decision (verbatim):** "Remove the login gate entirely" — the site must open with **no auth prompt**, on every route including `/`, `/glossary` and all `/api/*`.

---

## 1. Approach

The refactor was kept **mechanical and provable**, not clever:

- `verify_user` and its dependency were **deleted outright** (not stubbed to a no-op), and the
  66 `user: str = Depends(verify_user)` parameters were removed from the route signatures.
  Deleting the dependency is stronger than a no-op stub: there is no auth code path left to
  accidentally re-arm, and no `Depends`/`security` object remains.
- The removal was performed by a single scripted pass, then **proven equivalent** two independent
  ways (§3): an AST diff of every route, and a full OpenAPI schema diff against `git HEAD`.
- Nothing else in the route bodies was touched. `secrets.compare_digest`, `HTTPException`,
  `status`, `Header` and `Query` all stay imported because **non-auth** code still uses them
  (notably the webhook token check at `/api/webhook/ingest`).

## 2. `terminal_api.py` — before / after

### Before (`git HEAD` = `dff9aeb`)

```python
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Header, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
...
load_dotenv()
APP_USER = os.getenv("ADMIN_USER", "ankit")          # default username
APP_PASS = os.getenv("ADMIN_PASS", "<DEFAULT-PASSWORD>")   # literal redacted here
API_HOST = os.getenv("API_HOST", "127.0.0.1")
security = HTTPBasic()
...
def verify_user(credentials: HTTPBasicCredentials = Depends(security)):
    user_ok = secrets.compare_digest(credentials.username, APP_USER)
    pass_ok = secrets.compare_digest(credentials.password, APP_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login",
            headers={"WWW-Authenticate": "Basic"})
    return credentials.username


@app.get("/")
def root(user: str = Depends(verify_user)):
    return FileResponse("terminal/static/index.html")
```

### After

```python
from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Header, Query
...
load_dotenv()
API_HOST = os.getenv("API_HOST", "127.0.0.1")
...
@app.get("/")
def root():
    return FileResponse("terminal/static/index.html")
```

Deleted: the `HTTPBasic`/`HTTPBasicCredentials` import, `APP_USER`, `APP_PASS`,
`security = HTTPBasic()`, the whole `verify_user()` function, and the now-unused `Depends` import.
`API_HOST` and `load_dotenv()` were kept byte-for-byte.

### Routes changed — explicit count

| Metric | Count |
| --- | --- |
| `user: str = Depends(verify_user)` parameters removed | **66** |
| Route functions carrying the dependency (before) | 66 |
| Total route functions in the module | 68 |
| Total route decorators / OpenAPI operations | 68 / 67 |
| Routes that never had the Basic gate (correctly untouched) | `POST /api/webhook/ingest` (own token check) + 1 duplicate-decorator function |

`POST /api/webhook/ingest` keeps its **own** `X-Webhook-Token` (or `payload.token`) check and its
`401 "bad webhook token"` response — that is a webhook secret check, **not** the login gate, and it
was deliberately preserved. With no token configured it still returns **503** "webhook not
configured", exactly as before.

## 3. Proof that only auth changed

### 3a. AST equivalence (scripted)

```
Depends(verify_user) occurrences removed: 66
route functions compared: 68
routes whose signature lost exactly the `user` param: 66
route args_total before: 138 after: 72
route decorators total before: 68 after: 68
problems: 0
non-route defs before: ['_jsonable', '_league_mode', '_run_swing_scan_job', 'get_conn', 'safe_float', 'verify_user']
non-route defs after : ['_jsonable', '_league_mode', '_run_swing_scan_job', 'get_conn', 'safe_float']
```

Every route's decorator list, parameter list (minus `user`), defaults, return annotation and
**full body source** were compared before vs after: **0 problems**.

### 3b. OpenAPI diff vs `git HEAD` (pre-change file loaded in memory)

```
HEAD routes: 67  current routes: 67
route (path,method) set identical: True
operations differing after security is stripped: 0
--- security removed (raw, before stripping) ---
HEAD securitySchemes: ['HTTPBasic']
current securitySchemes: []
HEAD ops carrying a security block: 66
current ops carrying a security block: 0
HEAD ops actually ENFORCING security (non-empty list): 66
current ops actually ENFORCING security (non-empty list): 0
entire OpenAPI schema identical once security is stripped: True
PROOF OK
```

This is the strong form of the acceptance criterion: **route paths, methods, parameters, request
bodies, response codes and response models are byte-identical**; the *only* schema delta is the
disappearance of the security requirement.

## 4. `glossary_ui.py` — deliberately NOT modified (scope change)

Mid-task the Lead removed `glossary_ui.py` from this task's write scope (a sibling task, task-5,
now owns it). Recorded here for transparency:

1. I **had** already edited it — a single docstring line, `def glossary(user: str = Depends(verify_user)):`
   → `def glossary():` in the usage example (line 16). No executable code.
2. I verified with `git diff` that this was the **only** change in the file, then reverted it with
   `git checkout -- glossary_ui.py`. The file went back to a **clean HEAD base** (`dff9aeb`) for task-5.
3. **`glossary_ui.py` contains no routes at all** — it is a `render()` helper plus that docstring
   example. The real `/glossary` route lives in `terminal_api.py`
   (`@app.get("/glossary", response_class=HTMLResponse)` → `glossary_ui.render()`), so removing the
   dependency from `terminal_api.py` is what makes `/glossary` public. No router dependency in
   `glossary_ui.py` needed to "resolve".
4. `/glossary` verified unauthenticated: **HTTP 200**, 33 454 bytes, page title
   "What things mean - NSE Terminal", 27 rendered term sections.
5. The current working-tree modification to `glossary_ui.py` is task-5's own change
   (`GLOSSARY_SECTIONS` fallback in `render()`) — **not mine**.

## 5. `verify_deployment.py` — credential literal deleted

### Before (lines 165-166)

```python
        r = requests.get("http://127.0.0.1:8000/api/health",
                         auth=("<OWNER-USER>", "<OWNER-PASSWORD>"), timeout=5)
```

### After

```python
        api_base = os.getenv("API_BASE", "http://127.0.0.1:8000")
        r = requests.get(f"{api_base}/api/health", timeout=5)
```

- The hardcoded username/password tuple is gone; the script contains **no credential**.
- No default password was reintroduced anywhere.
- Since the login gate no longer exists, **no credentials are needed** to hit `/api/health`; the
  host is now overridable via the `API_BASE` env var, and the default preserves the previous
  `http://127.0.0.1:8000` target exactly.

## 6. Audit tooling — now works unauthenticated

The seven files were all moved to the same rule: **credentials are OPTIONAL and sent only when both
halves are explicitly supplied** (`ADMIN_USER` **and** `ADMIN_PASS`, or both `--user`/`--pass`).
With neither set, the default path sends **no `Authorization` header at all**.

| File | Change |
| --- | --- |
| `tools/ui-audit/audit.mjs` | `user`/`pass` defaults → `""`; `authHeader` becomes `null` unless both halves set; new `withAuth()` helper; preflight now expects **200**; a 401 is reported as a **stale/gated target** with a fix hint instead of "bad credentials"; `--help` text updated; CDP header call now `withAuth({ "Cache-Control": "no-cache" })` so `Cache-Control` is always sent |
| `tools/ui-audit/serve.mjs` | `user`/`pass` defaults → `""`; `auth` object is `{}` unless both are set; 401 message reworded; CLI usage text updated |
| `tools/ui-audit/probe.mjs` | defaults → `""`; conditional `authHeader`; `setExtraHTTPHeaders` only called when a header exists; explicit 401 message; help text updated |
| `tools/ui-audit/eval.mjs` | hardcoded `"<OWNER-USER>:<DEFAULT-PASSWORD>"` removed; header sent only when both env vars are set |
| `tools/ui-audit/shot.mjs` | same as `eval.mjs` |
| `tools/ui-audit/cssprobe.mjs` | defaults → `""`; header sent only when both env vars are set |
| `tools/ui-audit/README.md` | *see §7* |

The literal default password strings are gone from all of them. `node --check` passes on all six
`.mjs` files.

## 7. Extra files scrubbed (extended authorization)

The Lead authorized a minimal scrub beyond the original scope. Changes:

| File | Before (redacted) | After |
| --- | --- | --- |
| `PROJECT_HANDOFF.md:38` | `- Login: ADMIN_USER=…, ADMIN_PASS=<OWNER-PASSWORD> (stored in ~/nse-system/.env on VM; change anytime)` | `- Login: disabled — no auth gate; the HTTP Basic gate was removed from terminal_api.py (no credentials stored)` |
| `tools/ui-audit/README.md:34-37` | "The API is protected by HTTP Basic auth. Defaults are `<OWNER-USER>` / `<DEFAULT-PASSWORD>` …" | "The API has no login gate (the HTTP Basic layer was removed from `terminal_api.py`) …" (same 4-line block) |
| `tools/ui-audit/README.md:23` | "polls `/api/health` (HTTP Basic, max 40 s)" | "polls `/api/health` (no auth, max 40 s)" |
| `tools/ui-audit/README.md:63-64` | `--user <OWNER-USER> --pass <pw>` with comment "custom credentials" | `--user <user> --pass <pw>`, comment "optional: only if a target is gated again (both halves are required)" |
| `tools/ui-audit/README.md:122` | "sets the Basic-auth header." | "sets `Cache-Control: no-cache` (plus the optional Basic-auth header when credentials are configured)." |
| `.agents/AGENT_SETUP.md:161-162` | "…hardcodes `<OWNER-USER>/<OWNER-PASSWORD>`… rotate the credential." | "…hardcoded an owner credential (FIXED, auth gate removed)… no password remains; the API check reads `API_BASE` from env." |
| `.agents/MEMORY.md:218` | "hardcodes `<OWNER-USER>/<OWNER-PASSWORD>` \| rotate + read from env" | "hardcoded a credential (FIXED) \| login gate removed; no password stored" |
| `.agents/cache/FINDINGS.md:285-292` | F-16 `OPEN`, quoting the hardcoded `auth=(…)` tuple and the `<DEFAULT-PASSWORD>` default | F-16 `FIXED`, credential values removed, describes the fix |
| `.agents/cache/JOIN_HERE.md:187` | "\| F-16 \| LOW \| …hardcodes credentials `<OWNER-USER>/<OWNER-PASSWORD>` \|" | "\| F-16 \| FIXED \| …hardcoded a credential (scrubbed; login gate removed) \|" |
| `.agents/cache/env_index.json:178-182` | generated index entry `terminal_api.py:19 → APP_PASS = os.getenv("ADMIN_PASS", "<DEFAULT-PASSWORD>")` | stale entry deleted (line no longer exists); JSON re-validated |

Per the Lead's instruction, the historical fact *"the login gate was removed"* is preserved in each
doc; only the **usable credential value** was removed. Line counts were kept stable except where
deleting a stale generated index entry was the correct fix.

## 8. Grep evidence (item 5) — whole repo, all file types

Scope: `Get-ChildItem -Recurse -File -Force` over the repo root, **excluding** `env/`,
`node_modules/` and `.git/` (this deliberately includes gitignored artifacts such as
`.agents/**`, `tools/**/out/**` and `__pycache__/**`, which a default ripgrep sweep would skip).
**516 files scanned.**

> **Self-reference note.** This report necessarily names the identifiers it documents, so a raw
> grep of the final tree also matches *this file*: `HTTPBasic` ×7 lines, `verify_user` ×15,
> `ADMIN_PASS` ×6, `ADMIN_USER` ×5. The counts in the table below **exclude this report**, i.e. they
> are the counts over the application/tooling/doc files. The two required credential patterns are
> **0 even including this report** (it redacts them).

| Pattern (redacted label) | Hits (excl. this report) | Verdict |
| --- | --- | --- |
| `<OWNER-PASSWORD>` — the real password formerly in `verify_deployment.py` | **0** | ✅ zero — required (`0` including this report) |
| `<DEFAULT-PASSWORD>` — the old in-code default password | **0** | ✅ zero — required (`0` including this report) |
| `HTTPBasic` | **0** | ✅ eliminated from all code; only this report mentions it |
| `verify_user` | 10 | see below |
| `ADMIN_PASS` | 18 | see below |
| `ADMIN_USER` | 18 | see below |

### `verify_user` — 10 remaining hits (all documentation/build artifacts, no credentials)

```
glossary_ui.py:16                       (task-5's file — stale docstring example, see §4)
.agents/MEMORY.md:168                   (rule text: "Depends(verify_user) is silently public. Always add it.")
.agents/SUBAGENTS.md:188                (rule text: "every new route needs Depends(verify_user)")
.agents/cache/FINDINGS.md:129           (F-05 historical finding)
.agents/cache/FINDINGS.md:134           (F-05 historical finding)
.agents/cache/FINDINGS.md:137           (F-05 historical finding)
.agents/cache/FINDINGS.md:454           (historical route inventory)
.agents/cache/JOIN_HERE.md:148          (F-05 summary)
.agents/cache/system_map.json:2300      (generated symbol index)
__pycache__/glossary_ui.cpython-314.pyc:17  (compiled build artifact)
```

None of these is a credential. `.agents/MEMORY.md:168` and `.agents/SUBAGENTS.md:188` are now
**stale/actively misleading** instruction text (they tell future agents to add a dependency that no
longer exists) — flagged for the Lead in §11, **not** edited here.

### `ADMIN_PASS` (18) and `ADMIN_USER` (18) — variable **names**, no values

```
to do list.txt:7                        (names only — left untouched per Lead)
.agents/cache/api_index.json:378,379    (stale generated list terminal_api_env_vars, names only)
tools/ui-audit/audit.mjs:61,62,126,749
tools/ui-audit/serve.mjs:110,111,166,182,263
tools/ui-audit/probe.mjs:37,38,196
tools/ui-audit/eval.mjs:64,65,66
tools/ui-audit/shot.mjs:64,65,66
tools/ui-audit/cssprobe.mjs:57,58,59
tools/ui-audit/README.md:36
```

All are the *optional-auth env var names* that the audit tooling now reads; every one defaults to
`""` and none carries a value. No `console.log`/`--help` output prints a credential.

### Deliberate non-credential exceptions verified

- **89** case-insensitive `ankit` hits remain in the repo and are **not** credentials:
  78 are the Windows path `C:\Users\Ankit\...`, 7 are the GitHub username
  `ankitchaudhary6886`, 4 are owner-name prose (`Ankit's Instructions`, `Owner: Ankit`).
- Credential-style default username in an example command (`--user` + the owner's first name):
  **0** remaining — the one in `tools/ui-audit/README.md` was removed.
- Deploy/service scripts (`.bat`, `.ps1`, `.sh`, `.service`, `.yml`, `.yaml`, `.env`, 6 files found):
  **no** `ADMIN_*`, `auth=`, `--user`, `--pass` or `Basic ` literals.
- A scan for other credential-shaped literals (`passwd`, `"password" =`, `pwd = "…"`,
  `PASSWORD = "…"`) returned **no credential values**; the single `PASSWD` hit is the
  secret-scanner regex in `.agents/build_cache.py:358`.
- **No new credential value was found** that the Lead had not already listed. The only credential
  occurrences discovered beyond the original scope were the five `.agents/**` references to the two
  already-known strings (§7); all were scrubbed and are called out here for review.

## 9. Verification actually run

### a. Server

```
.\env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8013   # background job
```
Booted cleanly, no import/auth errors. (Port **8013** used deliberately to avoid the chart
teammate on 8012.)

### b. curl — with **NO** `Authorization` header

| Request | Status | Note |
| --- | --- | --- |
| `GET /` | **200** | |
| `GET /api/health` | **200** | body `{"ok":true,"prices_rows":1130292,"time":"2026-10-07T20:02:03.389042"}` — JSON, not a 401 |
| `GET /glossary` | **200** | 33 454 bytes, title "What things mean - NSE Terminal", 27 term sections |
| `GET /static/style.css` | **200** | static mount unaffected |
| `GET /api/explain` | **200** | |
| `GET /api/strategies` | **200** | |
| `GET /api/nope` | 404 | non-auth error behaviour unchanged |
| `POST /api/strategies/seed` | **200** | previously 401 — body `{"seeded":0}` |
| `POST /api/league/simulate` | **200** | previously 401 |
| `POST /api/webhook/ingest` (no token) | **503** | pre-existing webhook check preserved, **not** 401 |

Credentials are **ignored, not checked** — a deliberately WRONG Basic header still returns 200:

| Request with wrong credentials | Status |
| --- | --- |
| wrong Basic header on `/` | **200** |
| `--user totally:wrong` on `/api/health` | **200** |
| `--user <owner>:not_the_password` on `/glossary` | **200** |

Response headers for `/` contain `HTTP/1.1 200 OK` and **no `WWW-Authenticate`** challenge, so no
browser login dialog can be triggered.

### c. Tests — every repo-root `test_*.py`, run from the repo root

| Test file | Result |
| --- | --- |
| `test_backtest_integrity.py` | **PASS** (exit 0, 4 tests, OK) |
| `test_data_sources.py` | **PASS** (exit 0, 5 tests, OK) |
| `test_fundamentals_integrity.py` | **PASS** (exit 0, 6 tests, OK) |
| `test_kite_import.py` | **PASS** (exit 0, 5 tests, OK) |
| `test_kite_reconcile.py` | **PASS** (exit 0, 3 tests, OK) |
| `test_ml_integrity.py` | **PASS** (exit 0, 3 tests, OK) |
| `test_research_cockpit.py` | **PASS** (exit 0, 5 tests, OK) |
| `test_scanx_import.py` | **PASS** (exit 0, 2 tests, OK) |
| `test_sizing_safety.py` | **PASS** (exit 0, 3 tests, OK) |

**9/9 pass, exit 0.** No test asserts on 401/`Authorization`, and none needed changing.

### d. ui-audit harness — unauthenticated, 375 px

```
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8013 --viewports 375x812 --settle 5000
```

```
[audit] preflight OK  http://127.0.0.1:8013/ -> 200 (44216 bytes)
viewport   route          overflowPx  offenders  pageLvl  badWrap  textOut  status
375x812    #research      0           755        0        0        0        PASS
summary: 1/1 viewport-routes clean; mobileOverflowFailures=0; worstPageOverflowPx=0
audit exit code: 0
```

The harness reaches the app with **no credentials** and reports green (exit 0). Note `audit.mjs`
has `--server-port`, not `--port`, so `--url` was used against the already-running server; the
`--spawn-server` path was also updated to poll health with no auth.

### e. Cleanup

The port-8013 uvicorn background job was stopped and the port confirmed free after verification.

## 10. Deliberately not touched

- `terminal/static/**` — owned by the chart-rework teammate.
- `package.json`, `package-lock.json`, `explain.py`, `PORTAL_REDESIGN.md`, every `test_*.py`,
  `glossary_ui.py` (after the scope change) — other owners / not in scope.
- `POST /api/webhook/ingest` token check and its `401 "bad webhook token"` — a webhook secret
  check, not the login gate.
- `to do list.txt:7` — names the env var keys but **no values**; left untouched per the Lead.
- `.agents/cache/api_index.json:378-379` — a **stale generated list** of env var *names* (no
  values); left in place rather than hand-editing a generated cache.
- The 89 non-credential `ankit` mentions (Windows paths, GitHub username, owner prose).
- No repo-wide formatter was run.

## 11. Open follow-ups for the Lead (not actioned here)

1. **Stale auth guidance** in `.agents/MEMORY.md:168` and `.agents/SUBAGENTS.md:188` still tell
   future agents that every new route needs `Depends(verify_user)`. That dependency no longer
   exists and copying the advice would fail. These are curated instruction files, so I left them
   for the Lead to decide.
2. **Stale docstring** in `glossary_ui.py:16` still shows `def glossary(user: str = Depends(verify_user))`.
   Harmless (docstring only), but task-5 owns that file.
3. **Stale generated caches** referencing the removed symbols/env vars:
   `.agents/cache/api_index.json:378-379`, `.agents/cache/system_map.json:2300`,
   `.agents/cache/FINDINGS.md:129-137,454`, `.agents/cache/JOIN_HERE.md:148`,
   `__pycache__/glossary_ui.cpython-314.pyc`. Regenerating the caches is the clean fix.
4. **Neighbouring concern discovered during this task (out of scope):** no route returns a
   security challenge any more, so `/api/*` — including state-changing POSTs such as
   `/api/strategies/seed`, `/api/strategies/run-all` and `/api/league/replay` — is now fully open
   to anyone who can reach the host. That is the owner's explicit decision, but if the VM port
   8000 stays exposed to `0.0.0.0/0` the app should be protected at the network layer (or the
   gate intentionally restored) before public exposure.

## 12. Self-assessment

- Acceptance criteria met: `/` and `/api/health` return 200 without an `Authorization` header;
  both credential literals are at **0 hits** outside `env/` and `node_modules/` (including in this
  report, which redacts them); all `test_*.py` pass; the ui-audit harness is green at 375 px against
  the unauthenticated server; this report is written.
- Residual risk: low. The only functional delta in the application is the removal of the auth
  dependency, proven by an OpenAPI diff that is identical once `security` is stripped. The
  `server` and `.agents` files changed are tooling/docs, not request-handling code.
