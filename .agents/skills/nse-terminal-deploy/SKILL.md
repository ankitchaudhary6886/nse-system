---
name: nse-terminal-deploy
description: Use when shipping any change to the NSE Intelligence Terminal — produces whole copy-paste deploy blocks (Laptop PowerShell / SSH / VM) per owner rule R47, applies the correct restart rule, and requires verification output before success is claimed.
---

# NSE Terminal — Safe Deploy

Owner rule R47: **every** git and VM step is a whole copy-paste block, every
time. This skill turns "I changed a file" into a deploy the owner can execute on
a phone without improvising.

## 1. Decide the path from the change type

| Change | Restart needed? | Cache bump? | Verification |
|---|---|---|---|
| Backend `.py` (`terminal_api.py`, any root module) | **Yes** — `sudo systemctl restart nse-terminal` | no | `systemctl status` + `journalctl -n 300` |
| `terminal/static/*.js` / `.css` / `index.html` | **No** | **Yes** — bump `?v=` in `index.html` | page loads; endpoint returns 200 |
| `traders/*.py` or `strategy_config.SETUP/.SCREENER` | Yes | no | `trader_league.py selftest` → `28/28`, then `replay --changed --background` |
| `db.py` schema / `MIGRATIONS` | Yes | no | `python -c "import db; db.get_conn()"` then re-run the affected job |
| Documentation only (`*.md`) | No | no | none |
| Data / CSV import | No | no | the importer's own preview + post-apply report |

Current asset versions (authoritative): `.agents/cache/api_index.json` →
`asset_versions.script_tags`. As of the last cache build: `app.js?v=19`,
`style.css?v=19`, `league.js?v=20`, `cards.js?v=18`, `scanners.js?v=17`,
`research*.js?v=18`, `strategies.js?v=18`, `strategy_runs.js?v=18`,
`traders.js?v=18`, `strategy_editor.js?v=16`.

## 2. Emit exactly three blocks

Never merge them, never use a placeholder, never say "same as before".

**Block 1 — Laptop PowerShell** (commit + push):
```powershell
cd C:\Users\Ankit\Desktop\nse_system
git add .
git commit -m "nse: <what changed and why, one line>"
git push
```
Expected: `main -> main` and a commit hash line.

**Block 2 — SSH connect**:
```powershell
ssh -i C:\Users\Ankit\.ssh\nse.pem ubuntu@140.238.226.249
```
Expected: `ubuntu@<host>:~$`

**Block 3 — VM** (pull, restart, verify) — adapt the verification line to the
change type:
```bash
cd ~/nse-system
git pull
sudo systemctl restart nse-terminal
sleep 20
systemctl status nse-terminal --no-pager | head -5
sudo journalctl -u nse-terminal -n 300 --no-pager
```
Expected: `Active: active (running)` and no new traceback in the last 300 lines.

For a **static-only** change, replace the restart line with nothing and instead
tell the owner: hard-refresh the browser (phone: incognito, or append `?v=2`).

## 3. Verify with the artifact's own output

Pick the narrowest check that proves the change, and show the expected output:

```bash
source venv/bin/activate
python verify_deployment.py          # table freshness + service reachability
python trader_league.py selftest     # 28/28 checks passed
python data_quality.py               # 6 checks
python -c "from data_sources import get_registry; print(get_registry().health())"
tail -20 data/logs/scheduler.log
```

Remember: **`journalctl` is UTC, scheduler times are IST** (IST = UTC + 5:30).
An empty log window at 16:20 IST is 10:50 UTC.

## 4. Rollback is part of the deploy

```bash
cd ~/nse-system
git log --oneline -5
git revert <commit>
sudo systemctl restart nse-terminal
systemctl status nse-terminal --no-pager | head -5
```
For a single file: `git checkout -- <file>`. For the DB, restore a backup
(`data/app.db.pre-*` files are created by the import/reconcile scripts).

## 5. Rules that bite

- **Whole files only.** If a fix requires editing a file, ship the entire file
  content — not a diff the owner must splice.
- **Never restart before `git pull` succeeds.** A failed pull plus a restart
  leaves the old code running and looks like a deploy.
- **Never claim success without the status/journal output.** If you have not
  seen `Active: active (running)` after the restart, say the deploy is
  unverified.
- **`reload=True` is in `terminal_api.py`'s `__main__` block only.** Production
  runs under systemd with uvicorn, so in-process state
  (`_SWING_SCAN_STATE`, `_TRADER_FULL_SCAN_CACHE`) is lost on every restart by
  design.
- **Do not deploy from the laptop's `data/`.** Those files are gitignored and
  stale.

## 6. If the change is data-related

Follow `.github/skills/nse-data-research/SKILL.md` instead of improvising:
preview, backup, apply, verify. ScanX/KITE importers are **dry-run by default** —
`--apply` is required and creates `data/app.db.pre-*` backups. Never run an
importer against the VM DB without a preview first.
