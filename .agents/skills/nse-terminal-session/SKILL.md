---
name: nse-terminal-session
description: Use at the start of any session that touches the NSE Intelligence Terminal — orients the agent from the derived cache instead of re-reading the repo, states what is verified broken, and enforces the owner's whole-file / copy-paste / verify-before-claiming rules.
---

# NSE Terminal — Session Bootstrap

Use this **first**, before reading source files. The repo is ~19 k lines of
Python across ~120 modules plus 15 trader books; re-deriving it every session
wastes the budget and produces stale conclusions.

## Step 1 — Load the derived facts (do not grep for these)

| Read | For |
|---|---|
| `.agents/MEMORY.md` | **First.** The permanent rules: git→push→VM-pull, whole files, restart discipline, IST/UTC. Immutable unless the owner changes them |
| `.agents/cache/JOIN_HERE.md` | What the system is, the 12-component map, the traps, current state |
| `.agents/cache/FINDINGS.md` | **Mandatory.** 25 verified defects — three are CRITICAL. Check before "fixing" anything |
| `.agents/cache/GLOSSARY.md` | Disambiguate domain vs system vocabulary |
| `.agents/cache/system_map.json` | Module lines, docstring, functions, `imported_by` (use before changing a signature) |
| `.agents/cache/db_index.json` | Table columns, live row counts, latest dates, schema gaps |
| `.agents/cache/api_index.json` | 62 routes, JS→endpoint usage, `?v=` cache-bust versions |
| `.agents/cache/jobs_index.json` | 19 IST cron jobs + the exact `daily_update` stage order |
| `.agents/cache/env_index.json` | venv, packages, external hosts, secret reads |

For code-relationship questions ("who calls this?", "what breaks if I change it?"),
`codegraph explore "<question>"` is indexed for this repo (2,991 nodes / 7,173 edges)
and returns verbatim source plus the blast radius.

If a cache artifact is older than the code (`MANIFEST.json` → `generated_at`),
rebuild it:
```powershell
.\env\Scripts\python.exe .agents\build_cache.py
```

## Step 2 — Establish which machine you are talking about

This determines whether any number you read is meaningful.

| Machine | Role | DB |
|---|---|---|
| Laptop `C:\Users\Ankit\Desktop\nse_system` | **edit** machine | `data/app.db` — **stale** (~40 days behind, F-01) |
| VM `140.238.226.249` (user `ubuntu`, `~/nse-system`) | **production** | fresh; owns all `league_*` tables |

`data/*.db` and `data/*.pkl` are gitignored, so each machine has its own data.
**Never quote a local row count as a production fact.** The laptop DB has no
`league_*` tables at all.

## Step 3 — The owner's rules are absolute

The living version of this list is `.agents/MEMORY.md`. The non-negotiables:

1. **Every change is pushed to git AND pulled on Oracle Cloud.**
   Laptop `git add/commit/push` → VM `cd ~/nse-system && git pull`. A change
   that is only on the laptop is not deployed; one that is only in the VM
   working tree is not saved.
2. **Whole files only.** Never hand back a partial edit, a fragment, or
   "replace these lines". A fragment once caused a full outage.
3. **Git + VM steps = whole copy-paste blocks** (rule R47). One complete block
   per place — Laptop PowerShell · SSH connect · VM. Each self-contained
   (`cd`, venv activation), one command per line, no placeholders, expected
   output shown after each block. Never "same as before".
4. **Verify before claiming success.** `systemctl status` + `journalctl`, or the
   command's own output. A zero exit code is not evidence.
5. **Restart discipline.** Backend `.py` → `sudo systemctl restart nse-terminal`.
   `terminal/static/*` → no restart, but **bump the `?v=`** in `index.html`.
   Trader/setup/scanner change → also `replay --changed --background`.
6. **Never `DROP`.** `CREATE TABLE IF NOT EXISTS`; upsert with
   `INSERT OR REPLACE` or `DELETE`+`INSERT`; new columns via `db.py:MIGRATIONS`.
7. **Every optional integration in `try/except`.** The UI must never blank.
8. **No paid services.** Oracle Always Free — avoid heavy concurrent jobs.
9. **Plain English, lists, no jargon without explanation.** Phone is the main
   screen; the owner is a beginner coder.

## Step 4 — Timezone and scheduling discipline

Scheduler cron times are **IST**. `journalctl` timestamps are **UTC**.
`IST = UTC + 5:30`. This is the single most common mis-read during triage.
Full job list: `.agents/cache/jobs_index.json`.

## Step 5 — Before you change anything, answer these

- Which component (C1–C12 in `JOIN_HERE.md` §3) does this belong to, and who
  else imports the file? (`system_map.json` → `imported_by`)
- Does the change move a number that the **Trader League** depends on? If it
  touches `strategy_config.SETUP/.SCREENER`, `setup.py`, `scanner.py`, or any
  `traders/*.py`, the `home`/book `code_hash` changes and a
  `trader_league.py replay --changed --background` becomes mandatory.
- Does it touch a gate order in `swing_live.scan()`? Re-read
  `JOIN_HERE.md` §2.3 first — the order is load-bearing.
- Is it gated by an owner decision? (ID71 legacy cleanup, real-money trading,
  Streamlit retirement, credential rotation, HTTPS — all **GATED**, do not act.)

## Step 6 — Wrap up (the close-out is not optional)

Run the checklist in `.agents/MEMORY.md` §16:

```powershell
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\python.exe .agents\memory.py        # validates + rebuilds + prints the deploy blocks
```

That script validates the skills, rebuilds `.agents/cache/*.json`, re-syncs the
codegraph index, and prints the git/VM blocks ready to paste. Then:

- Append a CHANGELOG line to `PROJECT_HANDOFF.md` §16 and an entry to `EXECUTION_LOG.md`.
- Record any new defect in `.agents/cache/FINDINGS.md`.
- If the session changed a *rule* or a fundamental fact, update `.agents/MEMORY.md`.
- **Push to git and pull on the VM.**

## Anti-patterns

- Grepping the whole repo for module names instead of reading `system_map.json`
  or asking `codegraph explore`.
- Running `verify_deployment.py` on the laptop and treating the result as a
  health verdict — the local DB is stale, so it reports failures that are not real.
- Proposing a framework, paid API, or new dependency. There is a
  core-vs-optional split in `requirements.txt` / `requirements-optional.txt`;
  respect it.
- Declaring a fix "deployed" without the verification output.
- Leaving a change unpushed, or pushed but not pulled on the VM. That is the
  most common way this project loses work.
