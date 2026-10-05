"""build_cache.py — deterministic system-index builder for nse_system.

Regenerates .agents/cache/*.json from the live repository + database.
Stdlib only (no pandas/lightgbm import), so it runs even on a broken venv.

Usage (from repo root):
    .\\env\\Scripts\\python.exe .agents\\build_cache.py
    .\\env\\Scripts\\python.exe .agents\\build_cache.py --quiet

Outputs (all overwritten, never appended):
    .agents/cache/system_map.json    modules, entrypoints, deps, owners
    .agents/cache/db_index.json      tables, columns, live row counts, freshness
    .agents/cache/api_index.json     FastAPI routes + static JS -> endpoint usage
    .agents/cache/jobs_index.json    scheduler jobs (IST) + pipeline stages
    .agents/cache/env_index.json     interpreter, packages, external hosts, secrets
    .agents/cache/MANIFEST.json      generation metadata + sha256 of each artifact
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".agents" / "cache"
DB = ROOT / "data" / "app.db"

SKIP_DIRS = {"env", "__pycache__", ".git", "node_modules", ".venv", "venv",
             "trading-agents-swarm", ".pytest_cache"}

# ---------------------------------------------------------------- helpers


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def py_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------- system map

PY_HEADER = re.compile(r'^"""(.*?)"""', re.S | re.M)
CLI_MAIN = re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']')


def docstring_of(src: str) -> str:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ""
    ds = ast.get_docstring(tree) or ""
    return " ".join(ds.split())[:300]


def top_names(src: str) -> dict:
    """Top-level function and class names."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {"functions": [], "classes": []}
    funcs, classes = [], []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
    return {"functions": funcs, "classes": classes}


def imports_of(src: str) -> list[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                mods.add(node.module.split(".")[0])
    return sorted(mods)


THIRD_PARTY_KEEP = {
    "pandas", "numpy", "requests", "yfinance", "fastapi", "uvicorn",
    "apscheduler", "pytz", "sklearn", "lightgbm", "joblib", "streamlit",
    "plotly", "matplotlib", "feedparser", "gspread", "dotenv", "torch",
    "transformers", "bs4", "lxml", "openpyxl", "PIL",
}


def build_system_map() -> dict:
    local_mods = {p.stem for p in py_files()}
    modules = {}
    for p in py_files():
        src = read_text(p)
        if not src.strip():
            continue
        names = top_names(src)
        mods = imports_of(src)
        modules[rel(p)] = {
            "lines": src.count("\n") + 1,
            "bytes": p.stat().st_size,
            "doc": docstring_of(src),
            "functions": names["functions"],
            "classes": names["classes"],
            "has_cli": bool(CLI_MAIN.search(src)),
            "imports_local": [m for m in mods if m in local_mods and m != p.stem],
            "imports_third_party": [m for m in mods if m in THIRD_PARTY_KEEP],
        }
    # reverse dependency: who imports each module
    imported_by: dict[str, list[str]] = {}
    for path, meta in modules.items():
        for dep in meta["imports_local"]:
            imported_by.setdefault(dep, []).append(path)
    for path, meta in modules.items():
        meta["imported_by"] = sorted(imported_by.get(Path(path).stem, []))
    return {"root": str(ROOT), "module_count": len(modules), "modules": modules}


# ---------------------------------------------------------------- db index

FRESHNESS_COLUMNS = ["date", "signal_date", "scan_date", "tag_date",
                     "prediction_date", "run_date", "created_at", "run_at",
                     "updated_at", "uploaded_at", "graded_at", "computed_at"]


def build_db_index() -> dict:
    idx: dict = {"db_path": rel(DB), "exists": DB.exists()}
    if not DB.exists():
        return idx
    st = DB.stat()
    idx["size_mb"] = round(st.st_size / (1 << 20), 1)
    idx["mtime"] = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    tbl = {}
    for t in tables:
        try:
            rows = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception as e:
            rows = -1
            tbl[t] = {"error": str(e)}
        cols = [{"name": r[1], "type": r[2], "pk": bool(r[5])}
                for r in conn.execute(f'PRAGMA table_info("{t}")')]
        info = {"rows": rows, "columns": cols}
        colnames = {c["name"] for c in cols}
        for c in FRESHNESS_COLUMNS:
            if c in colnames and rows:
                try:
                    mx = conn.execute(
                        f'SELECT MAX("{c}") FROM "{t}"').fetchone()[0]
                    if mx is not None:
                        info["latest"] = {"column": c, "value": str(mx)}
                        break
                except Exception:
                    pass
        tbl[t] = info
    conn.close()
    idx["table_count"] = len(tables)
    idx["tables"] = tbl

    # Schema declared in db.py vs tables actually present
    dbpy = ROOT / "db.py"
    declared = set()
    if dbpy.exists():
        declared = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)",
                                  read_text(dbpy)))
    # Tables created lazily at runtime (ensure_tables-style DDL elsewhere)
    runtime_tables: dict[str, str] = {}
    for p in py_files():
        if p.name == "db.py":
            continue
        for t in re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)",
                            read_text(p)):
            runtime_tables.setdefault(t, rel(p))
    idx["schema"] = {
        "declared_in_db_py": sorted(declared),
        "created_at_runtime_by": dict(sorted(runtime_tables.items())),
        "present_but_undeclared": sorted(set(tables) - declared
                                         - set(runtime_tables)),
        "absent_here_created_at_runtime": sorted(
            (set(runtime_tables) - set(tables))),
        "note": ("Tables under 'absent_here_created_at_runtime' do not exist in "
                 "the LOCAL data/app.db because the module that creates them "
                 "has not run on this machine. They exist on the VM. Absence "
                 "locally is a stale-data signal, not a code defect."),
    }
    return idx


# ---------------------------------------------------------------- api index

ROUTE = re.compile(
    r'@app\.(?P<method>get|post|put|delete|patch)\(\s*"(?P<path>[^"]+)"')
FETCH = re.compile(r'''(?:fetch|axios\.\w+)\(\s*[`'"]([^`'"]+)''')
APIREF = re.compile(r'''["'`](/api/[A-Za-z0-9_\-{}$./]*)''')


def build_api_index() -> dict:
    api_py = ROOT / "terminal_api.py"
    routes = []
    env_vars = []
    if api_py.exists():
        src = read_text(api_py)
        for m in ROUTE.finditer(src):
            line = src[:m.start()].count("\n") + 1
            routes.append({"method": m.group("method").upper(),
                           "path": m.group("path"),
                           "file": "terminal_api.py", "line": line})
        env_vars = sorted(set(re.findall(r'environ\.get\(\s*["\']([A-Z0-9_]+)["\']', src))
                          | set(re.findall(r'getenv\(\s*["\']([A-Z0-9_]+)["\']', src)))
    seen, uniq = set(), []
    for r in routes:
        k = (r["method"], r["path"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: (r["path"], r["method"]))

    static = ROOT / "terminal" / "static"
    consumers = {}
    versions = {}
    for js in sorted(static.glob("*.js")) + sorted(static.glob("*.html")):
        text = read_text(js)
        eps = sorted(set(APIREF.findall(text)))
        if eps:
            consumers[rel(js)] = eps
    index_html = static / "index.html"
    if index_html.exists():
        html = read_text(index_html)
        for m in re.finditer(r'src=["\']([^"\']+\.js[^"\']*)["\']', html):
            versions.setdefault("script_tags", []).append(m.group(1))
        for m in re.finditer(r'href=["\']([^"\']+\.css[^"\']*)["\']', html):
            versions.setdefault("style_tags", []).append(m.group(1))

    return {"route_count": len(uniq), "routes": uniq,
            "terminal_api_env_vars": env_vars,
            "static_consumers": consumers,
            "asset_versions": versions}


# ---------------------------------------------------------------- jobs index

JOB = re.compile(
    r'add_job\(\s*(?P<fn>\w+)\s*,\s*'
    r'(?P<trigger>CronTrigger\([\s\S]*?\)|\w+)\s*,\s*'
    r'id="(?P<id>[^"]+)"')

DAILY_RESULT = re.compile(r'results\["(?P<name>[^"]+)"\]\s*=\s*_safe\(')


def build_jobs_index() -> dict:
    path = ROOT / "scheduler_bg.py"
    jobs = []
    if path.exists():
        src = read_text(path)
        fn_doc = {}
        for m in re.finditer(
                r'def (_\w+_job)\(\):\s*(?:"""(.*?)""")?', src, re.S):
            fn_doc[m.group(1)] = " ".join((m.group(2) or "").split())
        for m in JOB.finditer(src):
            trig = " ".join(m.group("trigger").split())
            hm = re.search(r'hour=(\d+),\s*minute=(\d+)', trig)
            dow = re.search(r'day_of_week="([^"]+)"', trig)
            day = re.search(r'day=(\d+)', trig)
            jobs.append({
                "id": m.group("id"),
                "function": m.group("fn"),
                "ist_time": (f"{int(hm.group(1)):02d}:{int(hm.group(2)):02d}"
                             if hm else None),
                "day_of_week": dow.group(1) if dow else None,
                "day_of_month": day.group(1) if day else None,
                "trigger": trig,
                "doc": fn_doc.get(m.group("fn"), ""),
            })
        jobs.sort(key=lambda j: (j["ist_time"] or "99:99", j["id"]))

    stages = []
    du = ROOT / "daily_update.py"
    if du.exists():
        dsrc = read_text(du)
        matches = list(DAILY_RESULT.finditer(dsrc))
        for i, m in enumerate(matches, 1):
            end = matches[i].start() if i < len(matches) else len(dsrc)
            tail = dsrc[m.start():end]
            mod = re.search(r'__import__\("([^"]+)"\)', tail)
            imp_fn = re.search(r'__import__\("[^"]+"\)\s*\.\s*(\w+)\(', tail)
            modname = mod.group(1) if mod else None
            entry = imp_fn.group(1) if imp_fn else None
            if not modname:
                # dispatched through a local helper: _safe("x", helper)
                helper = re.search(
                    r'_safe\(\s*"[^"]+"\s*,\s*(\w+)\s*\)', tail)
                if helper:
                    hm = re.search(
                        r'def ' + re.escape(helper.group(1)) +
                        r'\(\):\n((?:[ \t]+.*\n?)+)', dsrc)
                    if hm:
                        body = hm.group(1)
                        im = re.search(r'^\s*import (\w+)', body, re.M)
                        modname = im.group(1) if im else None
                        calls = re.findall(r'(\w+)\(\)', body)
                        entry = ", ".join(
                            c for c in calls if c not in ("get_logger",))
            stages.append({
                "order": i,
                "stage": m.group("name"),
                "module": modname,
                "entry": entry,
            })
    return {"scheduler_file": "scheduler_bg.py", "job_count": len(jobs),
            "jobs": jobs, "daily_update_trace": stages[:40]}


# ---------------------------------------------------------------- env index

HOST = re.compile(r'https?://([A-Za-z0-9._\-]+)')
SECRET_HINT = re.compile(
    r'(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PEM|CREDENTIAL)', re.I)


def build_env_index() -> dict:
    hosts: dict[str, list[str]] = {}
    for p in py_files():
        src = read_text(p)
        for m in HOST.finditer(src):
            hosts.setdefault(m.group(1), [])
            if rel(p) not in hosts[m.group(1)]:
                hosts[m.group(1)].append(rel(p))
    secrets = []
    for p in py_files():
        for i, line in enumerate(read_text(p).splitlines(), 1):
            if SECRET_HINT.search(line) and "environ" in line or \
               SECRET_HINT.search(line) and "getenv" in line:
                secrets.append({"file": rel(p), "line": i,
                                "code": line.strip()[:140]})
    venv_py = ROOT / "env" / "Scripts" / "python.exe"
    pkgs = {}
    if venv_py.exists():
        try:
            out = subprocess.run(
                [str(venv_py), "-m", "pip", "list", "--format=freeze"],
                capture_output=True, text=True, timeout=120)
            for line in out.stdout.splitlines():
                if "==" in line:
                    k, v = line.split("==", 1)
                    pkgs[k.strip()] = v.strip()
        except Exception as e:
            pkgs = {"_error": str(e)}
    req = ROOT / "requirements.txt"
    reqopt = ROOT / "requirements-optional.txt"
    return {
        "venv_python": rel(venv_py) if venv_py.exists() else None,
        "venv_python_version": sys.version.split()[0],
        "core_requirements": [l.strip() for l in read_text(req).splitlines()
                              if l.strip() and not l.startswith("#")]
        if req.exists() else [],
        "optional_requirements": [l.strip() for l in read_text(reqopt).splitlines()
                                  if l.strip() and not l.startswith("#")]
        if reqopt.exists() else [],
        "installed_package_count": len(pkgs),
        "installed_packages": pkgs,
        "external_hosts": {k: sorted(v) for k, v in sorted(hosts.items())},
        "secret_reads": secrets[:60],
    }


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)

    builders = {
        "system_map.json": build_system_map,
        "db_index.json": build_db_index,
        "api_index.json": build_api_index,
        "jobs_index.json": build_jobs_index,
        "env_index.json": build_env_index,
    }
    written = {}
    for name, fn in builders.items():
        try:
            payload = fn()
        except Exception as e:  # never let one artifact kill the build
            payload = {"_error": f"{type(e).__name__}: {e}"}
        target = CACHE / name
        target.write_text(json.dumps(payload, indent=1, default=str),
                          encoding="utf-8")
        written[name] = sha256_file(target)
        if not args.quiet:
            print(f"wrote {rel(target)} ({target.stat().st_size} bytes)")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": ".agents/build_cache.py",
        "root": str(ROOT),
        "artifacts": written,
    }
    (CACHE / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    if not args.quiet:
        print(f"wrote {rel(CACHE / 'MANIFEST.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
