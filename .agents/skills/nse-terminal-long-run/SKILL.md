---
name: nse-terminal-long-run
description: Run long verification, audit, test, and build commands on the NSE terminal without stalling the agent session. Use whenever a command could run longer than about 60 seconds, or after any tool call is aborted or times out.
---

# Long-running commands on the NSE terminal

The bottleneck that stalls sessions on this repo is not the work — it is a
single foreground tool call that runs for minutes and gets aborted mid-flight.
A full layout matrix is 21 viewport x route combinations and can exceed any
reasonable call timeout. The fix is mechanical: **bound every call, chunk the
matrix, and stream progress.**

## Rule 1 — no unbounded foreground call

Any command that might exceed ~60s goes into a background job:

```
pwsh(run_in_background: true)  ->  returns a job id immediately
job_output(job_id)             ->  read progress without blocking
job_list()                     ->  see what is still running
job_kill(job_id, reason)       ->  stop one that stopped mattering
```

Never `Start-Sleep` in a loop waiting for a background job. Keep working on
something disjoint and read the result when it is notified or when you need it.

## Rule 2 — chunk the audit matrix

`tools/ui-audit/audit.mjs` renders a real browser per viewport-route pair.
Split it into batches of about 6 combinations so each call finishes in well
under a minute and prints a `summary:` line you can cite:

```
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8020 --routes research,funda,swing --viewports 375x812,390x844 --settle 6000
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8020 --routes ledger,system,traders,league --viewports 375x812,390x844 --settle 6000
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8020 --routes research,swing,ledger --viewports 1440x900,768x1024 --settle 6000
```

`--settle` is per-navigation. Lower it to 4000-6000 for matrix runs; raise it
to 9000-12000 only for a single targeted screenshot where async panels must
finish loading.

## Rule 3 — always filter the output

Raw audit output is hundreds of lines of offender detail. Keep the transcript
small and cite the verdict:

```
... | Select-String -Pattern '^summary|FAIL|ERROR' | Select-Object -Last 4
```

## Rule 4 — sequence tests one file at a time

`test_*.py` are plain scripts (no pytest in `env/`). Looping all of them in one
call is fine, but capture only the tail of each:

```
Get-ChildItem test_*.py | ForEach-Object { $o = .\env\Scripts\python.exe $_.Name 2>&1 | Out-String; if ($o -notmatch 'OK') { "FAIL $($_)"; $o | Select-Object -Last 8 } }
```

## Rule 5 — emit a progress heartbeat

Before starting a multi-step verification, state the plan with counts, and
after each batch report `n/m clean`. A session that prints

    1: research,funda,swing   -> 6/6 clean
    2: ledger,system,...      -> 8/8 clean

is visibly working. A session that goes quiet for three minutes looks frozen
even when it is not. If a long step is unavoidable, post one line saying what
is running and roughly how long it should take.

## Rule 6 — recover, do not restart

If a call is aborted or times out, the work already completed is still on disk
and in the job log. Re-list with `job_list()`, read the tail with
`job_output()`, and resume from the first *unfinished* batch. Do not re-run
batches that already printed a clean summary.

## Rule 7 — servers

Start uvicorn as a background job on a port nobody else is using (the audit and
chart work have historically used 8011-8020 and 8020). Verify readiness with a
short bounded poll, then kill the job when verification ends so the port frees:

```
pwsh(run_in_background: true): .\env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8020
```

## Rule 8 — never re-publish a secret while reporting on it

If a credential audit finds a live secret, the REPORT must not quote it. Writing
`the token is 86503310:AA...` into a markdown file puts the secret back into the
repository, undoing the scrub that prompted the audit. This actually happened:
an auth verifier quoted the owner's password 16 times and the old default 10
times as "evidence", and the report was committed before anyone noticed.

Write findings as a location and a shape, not a value:

- good: `data/tg_secret.txt:1 — live 46-char Telegram bot token (redacted)`
- good: `recoverable from commit 3aae9419 in PROJECT_HANDOFF.md:33`
- bad: the token, the password, a partial token with the middle elided, or a
  hash that can be cracked offline.

Before committing any report, run the same sweep the scrub used and expect ZERO
hits:

```
Get-ChildItem -Recurse -File -Include *.md,*.py,*.js,*.mjs,*.txt,*.json,*.html,*.css,*.bat,*.ps1,*.yml -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\env\\|node_modules|\\.git\\' } |
  Select-String -Pattern '<secret-a>|<secret-b>'
```

A verification report that contains the credential is a failed verification.

## Rule 9 — kill the Chrome tree, not just the process

`child.kill()` on Windows leaves the whole Chrome renderer tree alive. One
`eval.mjs` run leaked 11 processes and a temp profile. Every harness script that
spawns Chrome must use `taskkill /PID <pid> /T /F` on win32 when the child is
still running (`audit.mjs` is the reference implementation). Also: never kill
`chrome.exe` by name — the owner's own browser uses the same binary. Match on
`--user-data-dir=...\(eval|shot|audit|cssprobe|probe)-` and the creation time.

## Quick checklist

- [ ] Any call that could exceed 60s is a background job or a bounded batch
- [ ] Batches are about 6 viewport-route pairs
- [ ] Output is filtered to the `summary:` line
- [ ] Progress is reported as `n/m clean` between batches
- [ ] On abort, resume the unfinished batch rather than starting over
- [ ] No secret value appears in any report (sweep before committing)
- [ ] Servers are killed at the end
