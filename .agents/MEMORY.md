# MEMORY — the permanent rules of Ankit's NSE system

> **Read this before doing anything.** It is the short list of things that must
> never be forgotten. Detail lives in `.agents/cache/JOIN_HERE.md` (system map)
> and `.agents/cache/FINDINGS.md` (what is broken). This file is the durable
> memory: it survives chat resets.

Last updated: **2026-10-05**

---

## 1. THE DELIVERY PIPELINE — every change follows this, every time

```
LAPTOP:  edit file  →  git add .  →  git commit -m "..."  →  git push
ORACLE VM:  cd ~/nse-system  →  git pull  →  restart if needed  →  VERIFY
```

**Nothing is "done" until it is pushed to git AND pulled on Oracle Cloud.**
A change that exists only on the laptop is not deployed. A change that exists
only in the VM's working tree is not saved.

| Step | Where | Command |
|---|---|---|
| 1. Edit | Laptop | `C:\Users\Ankit\Desktop\nse_system` |
| 2. Commit + push | Laptop PowerShell | `git add .` → `git commit -m "nse: <what and why>"` → `git push` |
| 3. Connect | Laptop PowerShell | `ssh -i C:\Users\Ankit\.ssh\nse.pem ubuntu@140.238.226.249` |
| 4. Pull | VM | `cd ~/nse-system` → `git pull` |
| 5. Restart | VM, **backend .py only** | `sudo systemctl restart nse-terminal` |
| 6. VERIFY | VM | `systemctl status nse-terminal --no-pager \| head -5` and `sudo journalctl -u nse-terminal -n 300 --no-pager` |

## 2. WHEN to push — substantial changes only, but never forget

**Push + pull when there is a SUBSTANTIAL change in code. Not on every
edit.** Small doc tweaks, cache rebuilds and single comment fixes do not
warrant a deploy cycle.

Substantial = any of:
- a change to a backend `.py` module (especially `terminal_api.py`, `setup.py`,
  `scanner.py`, `swing_live.py`, `top_picks.py`, `meta_model.py`, `db.py`)
- a new module, endpoint, table, scheduler job, or trader
- a refactor touching more than one file
- a change to `strategy_config.py`, `requirements*.txt`, or any `traders/*.py`
- a data/schema migration

**UNPUSHED WORK IS REMEMBERED, NOT FORGOTTEN.** Until the three blocks below are
run, the change exists only on the laptop. Keep it on the pending list and say so
at the end of every turn. A refactor that is never pushed is a refactor that
gets lost.

**Pending right now (2026-10-05):** the B2 band-universe consolidation
(16 backend files) and the `EXECUTION_LOG.md` compaction are **committed locally,
not yet pushed, and not yet pulled on the VM**. The VM needs
`git pull` + `sudo systemctl restart nse-terminal` + the `journalctl` check.

## 3. R47 — ALWAYS whole copy-paste blocks

Every git + VM step comes as **three separate, self-contained blocks**:
**Laptop PowerShell · SSH connect · VM**. Each block:

- starts with `cd`, and `source venv/bin/activate` before any `python`
- has **one command per line**
- has **no placeholders**
- is followed by the **expected output**

Never inline a snippet. Never say "same as before". Never merge the blocks.
This rule exists because the owner works from a phone and pastes block by block.

## 4. R1 / R28 — WHOLE FILES ONLY

Send the **complete file** for any change. Never a find/replace fragment, never
a partial patch, never "replace lines 40-55".

> A fragment once caused a full outage. This is the single hardest rule.

## 5. Restart discipline — get this right or the deploy silently does nothing

| What changed | Restart? | Extra step |
|---|---|---|
| Backend `.py` (root module, `terminal_api.py`) | **YES** → `sudo systemctl restart nse-terminal` | — |
| `terminal/static/*.js` / `.css` / `index.html` | **NO** | **bump the `?v=`** in `index.html`, then hard-refresh (phone: incognito or `?v=2`) |
| `traders/*.py`, `strategy_config.SETUP/.SCREENER`, `setup.py`, `scanner.py` | YES | **also** `python trader_league.py replay --changed --background` |
| `db.py` schema / `MIGRATIONS` | YES | confirm with `python -c "import db; db.get_conn()"` |
| Docs / data / CSV only | NO | — |

## 6. VERIFY — never claim success without command output

- `sudo systemctl status nse-terminal --no-pager | head -5` → must say `Active: active (running)`
- `sudo journalctl -u nse-terminal -n 300 --no-pager` → must show no new traceback
- A zero exit code is **not** evidence. Read the table or the endpoint the change touched.
- **`journalctl` timestamps are UTC. Scheduler times are IST. `IST = UTC + 5:30`.**
  This is the #1 cause of wrong incident conclusions.

## 7. Two machines — never confuse them

| Machine | Role | Data |
|---|---|---|
| Laptop `C:\Users\Ankit\Desktop\nse_system` | **edit** machine | `data/app.db` is **STALE** (~40 days behind). Has **no** `league_*` tables |
| Oracle VM `140.238.226.249` (user `ubuntu`, `~/nse-system`) | **PRODUCTION** | fresh data; owns all League state |

`data/*.db` and `data/*.pkl` are gitignored → each machine keeps its own data.
**Never quote a laptop row count as a production fact. Never copy a DB between them.**

## 8. Access facts

- Terminal: `http://140.238.226.249:8000` (FastAPI, HTTP Basic login)
- Legacy Streamlit backup: `:8501` (optional service, dead code)
- VM service: `nse-terminal.service` → `uvicorn terminal_api:app --host 0.0.0.0 --port 8000`
- VM venv: **always `source venv/bin/activate` first**
- Secrets: `.env` on the VM; Telegram token in `data/tg_secret.txt` line 1, chat id line 2
- Scheduler runs inside the API process (started by its lifespan)

## 9. Database rules

- `CREATE TABLE IF NOT EXISTS`; upsert with `INSERT OR REPLACE` or `DELETE`+`INSERT`
- **NEVER `DROP`.** **NEVER `ALTER` destructively.**
- New columns go through `db.py:MIGRATIONS` (idempotent, applied on every connection)
- Preview → backup → apply → verify, for any data import
- Backups exist as `data/app.db.pre-*.bak`

## 10. Code rules

- **Universe queries:** never write `mcap_cr BETWEEN 1000 AND 8000` inline.
  Call `universe_helper.band_universe(conn, limit)` — pass the limit your old SQL
  used, or `None` for the whole band. 17 copies were consolidated 2026-10-05; the
  helper truncates by market cap **before** returning A–Z, so the selected set is
  identical. This was B2, the codebase's largest single-point-of-failure.
- Every optional integration (telegram, yahoo, nse, meta, sheets) stays in
  `try/except`. **The UI must never blank.**
- **Before executing, identify what changes and who is affected** — read
  `system_map.json.imported_by` or run `codegraph impact <symbol>` first. Plan the
  whole change set, then execute. Do not discover breakage one file at a time.
- `terminal_api.py` auth is **opt-in per route** — a new route without
  `Depends(verify_user)` is silently public. **Always add it.**
- Register literal routes **before** the same prefix's `{symbol}` catch-all.
- `/static`, `/docs`, `/redoc`, `/openapi.json` are unauthenticated — **no secrets there.**
- All tunable numbers belong in **`strategy_config.py`** (rule R22), not inline.
- Keep `requirements.txt` (core) and `requirements-optional.txt` (optional) split.
- New feature order: **new module → endpoint → view**.

## 11. Trader rules (the book library)

- **R30** — setup identification **only**. No execution, stop-loss, sizing or
  trailing logic in trader code.
- **R35** — every trader needs `_fmt_num` + `_try_emit` so one bad symbol can't kill a scan.
- **R40** — every signal carries `raw.exits` with `thesis` + `hard_number` +
  `condition`. Exits are **suggestive, not directive**.
- **R41** — mark overlaps with `overlaps_with`; **never prune a method**.
- **R42** — no proxies, no parameter tweaks. Missing data → ship **silent**, log the gap.
- **R43** — `LONG_ENTRY` vs `TOP_WARNING`. **No shorting.**
- **R44** — add the `EXIT_LOGIC.md` section. **R45** — add the wisdom artifact.
- Register in `traders/__init__.py` (explicit list, not auto-discovery).
- Any trader code change changes `code_hash` → **`replay --changed` is mandatory**.

## 12. Data rules

- A value enters replay/backtest **only** if both its **financial period end**
  and its **first public availability** are known. Undated = research only.
- A file's **modification time is not publication evidence**.
- A snapshot must **never** overwrite a newer daily bar.
- Promote **per field**, with before/after evidence. Withhold disagreements.
- ScanX / KITE imports are **dry-run by default**; `--apply` is explicit.

## 13. Safety rules

- **No paid services, ever.** Oracle Always Free — avoid heavy concurrent jobs.
- **Do not deploy real capital.** Trader League verdict is **NOT READY**
  (PF 0.93 vs the 1.3 bar; 0/30 live paper trades).
- **Do not touch ID71 legacy values** until the DR-01 v2 backfill is verified.
- Gated by the owner (do not act unless asked): credential rotation, HTTPS/domain,
  Streamlit retirement, Google Sheets sync.
- **Never `git push --force`.** Rollback = `git checkout -- <file>` or `git revert <commit>`.

## 14. Currently broken — check before assuming

| | Issue | Consequence |
|---|---|---|
| CRITICAL | `data/meta_model.pkl` is a bare estimator, not a versioned bundle | P(WIN) → Top Picks dead |
| CRITICAL | `data/ml_models.pkl` is `v0.1`, loader wants `v0.2-pit-safe` | `ml_predictions` empty → `scan` rejects everything |
| HIGH | `pattern_grades` = 0 rows, pattern gate = `{}` | the 60% pattern gate is vacuously open |
| HIGH | Laptop DB ~40 days stale | local numbers are not production |
| HIGH | `/static`, `/docs`, `/redoc` unauthenticated | secrets must never go in `terminal/static/` |
| — | `sizing.py` has no Kelly maths despite the name | caps only |
| — | `verify_deployment.py` hardcodes `ankit/ankitc21` | rotate + read from env |

Full evidence: `.agents/cache/FINDINGS.md` (25 entries).

## 15. Writing style (the owner works from a phone)

- **Plain English. Lists. No jargon without explaining it.**
- Give complete, copy-paste-ready code + exact commands + expected output.
- Minimise back-and-forth.
- Verify every deploy before declaring success.

## 16. Where to look

| Need | Read |
|---|---|
| Start of any session | `.agents/cache/JOIN_HERE.md` |
| Is it broken? | `.agents/cache/FINDINGS.md` |
| This file (rules) | `.agents/MEMORY.md` |
| Module / table / route / job facts | `.agents/cache/*.json` |
| Code relationships ("who calls this?") | `codegraph explore "<question>"` |
| Owner handoff + changelog | `PROJECT_HANDOFF.md` |
| Full rule archive | `git show 8ef71218:backlog.md` (R1–R42) |
| Recent decisions (last 6 entries full) | `EXECUTION_LOG.md` |
| Every past decision, full text | `EXECUTION_LOG_FULL.md` (pre-compaction archive) |
| Exit philosophy per book | `EXIT_LOGIC.md` |
| Deploy blocks A–K | `TRADER_LEAGUE.md` §2/§4/§8 |

## 17. Session close-out

1. `PROJECT_HANDOFF.md` §16 — append a CHANGELOG line.
2. `EXECUTION_LOG.md` — append the execution entry (recent 6 stay full; older
   ones live one-line in its index; full text is in `EXECUTION_LOG_FULL.md`).
3. `.agents/cache/FINDINGS.md` — record any new defect found or fixed.
4. Run the close-out: `.\env\Scripts\python.exe .agents\memory.py`
   (validates, rebuilds the cache, re-indexes codegraph, prints the deploy blocks).
5. Push to git **and** pull on the VM.
