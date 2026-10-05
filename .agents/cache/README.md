# .agents/cache — retrieval cache for the NSE Intelligence Terminal

**Purpose:** stop re-reading the repository on every new session. Read this
folder first; it holds the *derived* facts. Regenerate it when the code or DB
changes.

**Generated at:** see `MANIFEST.json` → `generated_at` (includes a SHA-256 per
artifact so you can tell whether the cache is current).

## Read order (cheapest first)

| Order | File | Size | What it answers |
|---|---|---|---|
| 1 | `../MEMORY.md` | small | **The permanent rules** — git→push→VM-pull, whole files, restart discipline, IST/UTC |
| 2 | `JOIN_HERE.md` | small | What this system is, the 12 components, what is broken |
| 3 | `system_map.json` | ~90 KB | Every module: lines, docstring, functions, classes, local + 3rd-party imports, reverse importers, has CLI |
| 4 | `db_index.json` | ~30 KB | Every table: columns, PK, **live row count**, latest date. Plus declared-vs-present schema gaps |
| 5 | `api_index.json` | ~10 KB | Every FastAPI route (method/path/file/line), static JS → endpoint usage, current `?v=` asset versions |
| 6 | `jobs_index.json` | ~6 KB | The 19 scheduler jobs with IST times, plus the exact `daily_update` stage order |
| 7 | `env_index.json` | ~4 KB | venv path, installed packages, external hosts, secret reads, requirements split |
| 8 | `FINDINGS.md` | small | 25 verified defects with severity + evidence + status. **Check before "fixing" anything** |
| 9 | `GLOSSARY.md` | small | Domain + system vocabulary |

## Regenerate

```powershell
.\env\Scripts\python.exe .agents\build_cache.py     # just the JSON artifacts
.\env\Scripts\python.exe .agents\memory.py          # full close-out: validate + cache + codegraph + deploy blocks
```

Both are stdlib-only — they work even if the venv is broken. Never hand-edit a
`.json` here; it will be overwritten. Hand-maintained files are `../MEMORY.md`,
`JOIN_HERE.md`, `FINDINGS.md`, `GLOSSARY.md`, and this README.

## Code intelligence

`codegraph` is indexed for this repo (`.codegraph/`, ~8.9 MB, gitignored).
Use it for relationship questions, not for facts already in the JSON above:

```powershell
codegraph explore "where is the fund veto applied before inserting a swing signal"
codegraph callers vetoed
codegraph impact SetupDetector
codegraph sync .          # re-index after edits (the MCP server auto-syncs)
```

It returns verbatim on-disk source plus the blast radius (callers, dependent
files, related tests), and correctly identifies the 62 API routes.

## Sanity rules

- `db_index.json` reflects the **machine it ran on**. The laptop DB is stale
  (see `FINDINGS.md` F-01); the VM DB is the one in production. Absence of a
  runtime-created table locally (`league_*`, `setup_pool`, `trend_candidates`,
  `value_radar`, `positional_picks`, `kite_market_snapshots`,
  `market_data_attestations`) is a *stale-laptop* signal, not a code defect.
- `system_map.json.modules[*].imported_by` is the fastest way to find every
  caller of a module before changing its signature.
- `api_index.json.asset_versions.script_tags` is the authoritative cache-bust
  list. Editing a static JS file without bumping its `?v=` serves a stale
  bundle (PROJECT_HANDOFF §4.3).
