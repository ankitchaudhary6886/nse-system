# AGENT_SETUP — what is installed, what was fixed, what is still open

Verified **2026-10-05**. The owner approved the recommendations; the **Applied**
section below records what was actually changed. Re-run the checks at the bottom
to refresh.

---

## 0. APPLIED THIS SESSION (owner-approved)

| # | Action | File(s) changed | Verified |
|---|---|---|---|
| 1 | Removed the dead `codebase-memory-mcp` server | `.vscode/mcp.json` | resolved before/after |
| 2 | Removed the dead `headroom` server | `.agents/mcp_config.json`, `.vscode/settings.json` | resolved before/after |
| 3 | Registered the working `codegraph` MCP server | `.vscode/mcp.json`, `.vscode/settings.json`, `.agents/mcp_config.json` | `codegraph serve --mcp` exists |
| 4 | Deduplicated the instruction registration (it was listed twice) | `.vscode/settings.json` | 2 entries → 1 |
| 5 | Added `env/` and index/state dirs to the Copilot exclusion list | `.copilotignore` | F-21 fixed at source |
| 6 | Ignored the machine-local code index | `.gitignore` (`.codegraph/`) | — |
| 7 | Built the code index | `.codegraph/` (2,991 nodes, 7,173 edges, 150 files, 8.89 MB) | `codegraph status` |
| 8 | Disabled codegraph telemetry | codegraph config | `telemetry off` |
| 9 | Wrote the permanent rules file | `.agents/MEMORY.md` | validated by `memory.py` |
| 10 | Wrote the close-out script | `.agents/memory.py` | runs clean, exit 0 |

**Deliberately NOT done**, with reasons:

| Recommendation | Why I skipped it |
|---|---|
| `pip install redcon` | It exists only to satisfy a *duplicated* `## Context Selection` paragraph in two agent specs. Installing a dependency to serve a redundant instruction is backwards. The better fix is deleting the paragraph |
| `pip install stockstats` for `trading-agents-swarm` | That directory is an **unrelated third-party clone** (F-23) that nothing in this repo imports. Installing dependencies for unused code adds maintenance without value |
| `npx esbuild` for JS checking | **Not needed.** `node --check` already syntax-validates all 12 static JS files and the inline `<script>` in `wisdom.html` — zero new dependency, and it passes today. See §4 |
| Editing `.github/agents/*.agent.md` | Those specs are non-executable in this environment and the user-level agent surface is not used by this repo's skills. Left intact; the Redcon removal is a one-line edit if you want it |
| Deleting user-level `~/.dsh/skills/clawhub-*` | `nse-orchestrator` is unrelated to this project (F-24) but is the owner's user-level install, not project state. Left alone; flagged instead |

---

## 1. Already working (no action)

| Item | Version / path | Used for |
|---|---|---|
| Python | **3.14.7** — `env\Scripts\python.exe` | the whole system |
| Node.js | **v24.18.1** — `C:\Program Files\nodejs\node.exe` | MCP servers, JS syntax checks |
| pnpm | **12.8.1** | not used by this repo (no `package.json`) |
| git | `D:\Program Files\Git\cmd\git.exe` | deploy |
| venv packages | **100** installed, including `fastapi 0.141.1`, `uvicorn 0.52.3`, `apscheduler 3.11.3`, `pandas 3.0.5`, `numpy 2.5.2`, `scikit-learn 1.9.0`, `lightgbm 4.7.0`, `joblib 1.5.3`, `yfinance 1.6.0`, `streamlit 1.61.1`, `matplotlib`, `plotly 6.9.0`, `torch 2.13.0+cpu`, `transformers 5.15.0`, `feedparser`, `gspread`, `python-dotenv`, `pytz`, `pyarrow 24.0.0` | core + all optional layers |
| DSH project skills | `.agents/skills/` (6 skills) | discovered by DSH at rank 200 |
| Retrieval cache | `.agents/cache/` | derived facts, no re-reading |
| Permanent rules | `.agents/MEMORY.md` | the git→push→VM-pull workflow and all owner rules |
| Close-out script | `.agents/memory.py` | validate + rebuild + re-index + print deploy blocks |
| `codegraph` | CLI **and** MCP server | code-relationship queries, blast radius |
| `token-cache` MCP | `…\sarfudheen.tokensculpt-1.0.19\dist\cache-server.js` | TokenSculpt semantic cache |
| `ctx-gate` hooks | `…\agent-context-gate\bin\ctx-gate.js` | session-cost warnings (enforcement is **off**) |

**The Python environment is complete.** The project does not need any new Python
package to run. Every remaining gap is documentation or third-party cleanup.

---

## 2. Still open — needs an owner decision

| Item | Configured in | Problem | Action |
|---|---|---|---|
| Redcon tools (`redcon_rank`, `redcon_pack`) | `.github/agents/planner.agent.md:75-80`, `implementer.agent.md:74-78` | extension installed; CLI missing; not registered in any MCP config | **Delete the duplicate `## Context Selection` paragraph** in both files. Do not install Redcon |
| `.agentflow/` | the 4 agent specs + `.github/skills/handoff/SKILL.md` | directory does not exist and is gitignored — every spec writes there | Create it (`.agentflow/.gitkeep`) if you use those specs, otherwise their output contract is unsatisfiable |
| `.context-ops/` | ctx-gate hooks | scaffold from 2026-10-02, never used: `learned.yml` empty, `standing.yml` all `hits: 0`, `answers.jsonl` absent; `manifest.json`/`glossary.yml` are polluted with FastAPI-tutorial routes | `env/` is now excluded, but the **stale index and glossary remain**. Delete `manifest.json` + `memory/glossary.yml` and let it regenerate, or ignore it — it is inert while `enforcement: 'off'` |
| `cache_lookup` / `skeleton_view` | `CLAUDE.md` | the literal tool names are not in the MCP server bundle; they come from extension-generated text | Treat as unavailable. Use `codegraph`, `grep`/`read`, and `.agents/cache` instead |

---

## 3. Instruction conflict — decide which wins

`CLAUDE.md` + `.github/instructions/tokensculpt.instructions.md` are an active
"managed block" that **contradicts the owner's own rules**:

| TokenSculpt says | Owner rule says |
|---|---|
| "Never reprint unmodified source files or entire classes"; diff-only edits | **R1/R28** — whole files only, ever. A fragment once caused a **full outage** |
| "Never run raw `git` commands directly in terminal" (`rtk` filters) | **R4/R34/R47** — explicit per-machine `git add/commit/push` copy-paste blocks. `rtk` is **not installed** |
| "Halt and ask the user after 3 failed attempts" | **R10** — no pausing, keep momentum |
| "Never read the same file more than 2 times per conversation" | Verification culture requires re-checking deployed state |

**Recommendation:** the owner's rules win (they describe past production
incidents). Either disable the TokenSculpt managed block, or add a one-line
override at the top of `CLAUDE.md`:

```markdown
<!-- OWNER RULES OVERRIDE THIS BLOCK: whole files only (R1/R28);
     git/VM steps as whole copy-paste blocks (R47); never use rtk (not installed). -->
```

Also note `.vscode/settings.json` previously registered the same instruction file
**twice** — that duplicate has now been removed (Applied #4).

---

## 4. Recommended installs — assessed

Each was evaluated against "does this actually help this system?". **No new
dependency was installed**, because for every case a zero-cost option already
existed.

| Want | Verdict | What to do |
|---|---|---|
| A real semantic-cache lookup over this repo | **No install needed** | `.agents/cache` + `grep` + `codegraph` is already better — it is derived from *this* repo, not a generic tool. TokenSculpt's `cache_lookup` never stored an answer |
| The ctx-gate semantic memory to work | **Config fix, not an install** | `env/` is now excluded (Applied #5). To finish: delete `.context-ops/manifest.json` + `memory/glossary.yml` and let them regenerate |
| `codegraph` as an agent tool | **DONE** (Applied #1-#3, #7, #8) | Registered in `.vscode/mcp.json`, `.vscode/settings.json`, `.agents/mcp_config.json`; index built; telemetry off |
| Redcon context packing | **Not worth it** | `pip install redcon` would exist only to serve a *duplicated* `## Context Selection` paragraph. Delete the paragraph instead |
| `trading-agents-swarm` to run | **Not worth it** | Unrelated third-party clone (F-23) that nothing imports. `stockstats` is its only missing import; installing deps for unused code is pure maintenance cost |
| JS syntax checking for `terminal/static/*.js` | **DONE with zero dependencies** | See below |

### JavaScript syntax checking — no `package.json` needed

`.github/skills/nse-terminal-ux` asks for JS checks, and the repo has no JS
tooling. `node --check` covers it without adding anything:

```powershell
cd C:\Users\Ankit\Desktop\nse_system
Get-ChildItem terminal\static\*.js | ForEach-Object {
  node --check $_.FullName
  if ($LASTEXITCODE -eq 0) { "OK    $($_.Name)" } else { "FAIL  $($_.Name)" }
}
```

**Current result: all 12 files pass.** `node --check` only sees external files,
so inline scripts need extracting. `wisdom.html` has one inline block (23,865
chars) and it also passes:

```powershell
.\env\Scripts\python.exe -c @"
import re, pathlib, subprocess, tempfile
t = pathlib.Path('terminal/static/wisdom.html').read_text(encoding='utf-8')
for i, b in enumerate(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', t, re.S), 1):
    p = pathlib.Path(tempfile.gettempdir()) / f'_chk_{i}.js'
    p.write_text(b, encoding='utf-8')
    r = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True)
    print(f'block {i}: ' + ('OK' if r.returncode == 0 else 'FAIL'))
"@
```

`esbuild` (0.28.2, available via `npx`) is a heavier alternative and is only
worth it if you later want bundling or minification — not for syntax checks.

**Do not install:** any paid data API, any hosted vector database, LangChain /
LangGraph (the swarm deliberately avoids them), or a second web server. The
system runs on Oracle Always Free and forbids paid services.

---

## 5. Housekeeping that matters more than any install

1. **F-17 — the entire agent layer is untracked.** `.agents/`, `.context-ops/`,
   `.github/{agents,hooks,instructions,prompts,skills/handoff}/`, `.vscode/`,
   `CLAUDE.md`, `.cavemanrc`, `.copilotignore`, `trading-agents-swarm/` are all
   `??` and **not** gitignored. A fresh clone or `git clean -fdx` loses the
   cache, the memory file and the skills. **Run `.agents/memory.py` and paste
   its three blocks** to commit and pull them on the VM.
2. **F-18 — R1–R43 rule text is unreachable** from `backlog.md` (only git history
   has it); R44/R45 are absent from §A; R46 is undefined. Restore from
   `git show 8ef71218:backlog.md`.
3. **F-21 — `.copilotignore` missed `env/`** — now fixed (Applied #5). The stale
   ctx-gate index and glossary still need deleting (§2).
4. **F-16 — `verify_deployment.py` hardcoded an owner credential (FIXED, auth
   gate removed).** No password remains; the API check reads `API_BASE` from env.
5. **F-05 — `/static`, `/docs`, `/redoc`, `/openapi.json` are unauthenticated.**

---

## 6. Re-run the checks

```powershell
cd C:\Users\Ankit\Desktop\nse_system

# everything at once: validate + rebuild cache + re-index + print deploy blocks
.\env\Scripts\python.exe .agents\memory.py

# binaries
foreach($c in @('node','pnpm','git','codegraph','headroom','codebase-memory-mcp','rtk','redcon')){
  $g = Get-Command $c -ErrorAction SilentlyContinue
  "{0,-22} {1}" -f $c, ($(if($g){"OK  -> " + $g.Source}else{"MISSING"}))
}

# venv
.\env\Scripts\python.exe --version
.\env\Scripts\python.exe -m pip list --format=freeze | Measure-Object -Line

# skills visible to DSH
Get-ChildItem .agents\skills -Directory | Select-Object -ExpandProperty Name

# code index
codegraph status .

# cache freshness
Get-Content .agents\cache\MANIFEST.json -Raw
```

To confirm DSH has picked up the skills, start a session in this directory and
call the `skill` tool — the six `nse-terminal-*` entries must appear in the
catalog alongside any user-level skills.

> **Name-collision warning (F-24).** A user-level skill named `nse-orchestrator`
> exists at `C:\Users\Ankit\.dsh\skills\clawhub-vveerrgg--nse-orchestrator`.
> Its "NSE" means **Nostr Sovereign Entity** and it installs `nostrkey`,
> `nostrwalletconnect` and friends. It is **not** related to this NSE India
> trading terminal. Never invoke it for this repo, and never follow its
> `pip install` instructions here.
