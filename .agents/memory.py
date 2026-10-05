"""memory.py — the session close-out for the NSE terminal.

One command that does everything `.agents/MEMORY.md` §16 requires:

  1. validate  — the 6 project skills parse, the cache artifacts are current
  2. cache     — rebuild .agents/cache/*.json from the live repo + DB
  3. codegraph — re-sync the code index (skipped cleanly if not installed)
  4. deploy    — print the three R47 copy-paste blocks, ready to paste

Stdlib only, so it runs even if the venv is broken.

Usage (from the repo root):
    .\\env\\Scripts\\python.exe .agents\\memory.py
    .\\env\\Scripts\\python.exe .agents\\memory.py --message "nse: fix pattern gate"
    .\\env\\Scripts\\python.exe .agents\\memory.py --no-codegraph

Exit code 0 = ready to deploy, 1 = a validation problem needs attention.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / ".agents"
CACHE = AGENTS / "cache"

OK = "  [OK]  "
BAD = "  [!!]  "
INFO = "  --    "

# Files whose change invalidates the Trader League code_hash.
LEAGUE_TRIGGERS = ("traders/", "setup.py", "scanner.py", "strategy_config.py")
# Files that need a systemd restart.
RESTART_TRIGGERS = (".py",)


def _ascii(text: str) -> str:
    """Keep console output readable under cp1252 (Windows PowerShell)."""
    return (text.replace("\u2014", "-").replace("\u2013", "-")
                .replace("\u2192", "->").replace("\u2019", "'"))


def run(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           timeout=timeout, shell=False)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def git(*args: str) -> str:
    code, out = run(["git", *args], timeout=60)
    return out.strip() if code == 0 else ""


# ------------------------------------------------------------------ 1. validate

def validate_skills(problems: list[str]) -> int:
    skills = sorted(AGENTS.glob("skills/*/SKILL.md"))
    if not skills:
        problems.append("no skills found under .agents/skills/")
        return 0
    for p in skills:
        text = p.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            problems.append(f"{p.relative_to(ROOT)}: missing YAML frontmatter")
            print(f"{BAD}{p.parent.name}: no frontmatter")
            continue
        fm = m.group(1)
        name = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
        desc = re.search(r"^description:\s*(.+)$", fm, re.M)
        issues = []
        if not name:
            issues.append("no `name:`")
        if not desc:
            issues.append("no `description:`")
        elif len(desc.group(1)) < 40:
            issues.append("description too short to be discovered reliably")
        if name and name.group(1) != p.parent.name:
            issues.append(f"name '{name.group(1)}' != directory '{p.parent.name}'")
        if issues:
            problems.extend(f"{p.relative_to(ROOT)}: {i}" for i in issues)
            print(f"{BAD}{p.parent.name}: {'; '.join(issues)}")
        else:
            print(f"{OK}{p.parent.name}")
    return len(skills)


def validate_cache(problems: list[str]) -> None:
    required = ["system_map.json", "db_index.json", "api_index.json",
                "jobs_index.json", "env_index.json", "MANIFEST.json"]
    for name in required:
        p = CACHE / name
        if not p.exists():
            problems.append(f"missing cache artifact .agents/cache/{name}")
            print(f"{BAD}{name}: missing")
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            problems.append(f".agents/cache/{name}: unreadable ({e})")
            print(f"{BAD}{name}: unreadable")
            continue
        if isinstance(payload, dict) and "_error" in payload:
            problems.append(f".agents/cache/{name}: builder error {payload['_error']}")
            print(f"{BAD}{name}: builder error")
        else:
            print(f"{OK}{name}")


def validate_memory(problems: list[str]) -> None:
    mem = AGENTS / "MEMORY.md"
    if not mem.exists():
        problems.append("missing .agents/MEMORY.md (the permanent rules file)")
        print(f"{BAD}MEMORY.md: missing")
        return
    text = mem.read_text(encoding="utf-8", errors="replace")
    # The rules that must survive edits to the file itself.
    must_have = [
        ("git", "pushes to git"),
        ("git pull", "pulls on the VM"),
        ("WHOLE FILES", "the whole-files rule"),
        ("R47", "the R47 copy-paste-block rule"),
        ("journalctl", "the verify step"),
        ("5:30", "the IST/UTC offset"),
        ("DROP", "the never-DROP rule"),
        ("try/except", "the optional-integration rule"),
        ("No paid services", "the no-paid-services rule"),
    ]
    missing = [label for needle, label in must_have if needle not in text]
    if missing:
        problems.append(f".agents/MEMORY.md lost: {', '.join(missing)}")
        print(f"{BAD}MEMORY.md: missing {len(missing)} required rule(s)")
    else:
        print(f"{OK}MEMORY.md ({len(text.splitlines())} lines, all key rules present)")


# ------------------------------------------------------------------ 2. cache

def rebuild_cache(problems: list[str]) -> None:
    code, out = run([sys.executable, str(AGENTS / "build_cache.py"), "--quiet"])
    if code != 0:
        problems.append(f"build_cache.py exited {code}")
        print(f"{BAD}cache rebuild failed: {out.strip()[:200]}")
    else:
        print(f"{OK}cache rebuilt from live repo + DB")


# ------------------------------------------------------------------ 3. codegraph

def resync_codegraph(enabled: bool, problems: list[str]) -> None:
    if not enabled:
        print(f"{INFO}codegraph: skipped (--no-codegraph)")
        return
    exe = shutil.which("codegraph")
    if not exe:
        print(f"{INFO}codegraph: not installed, skipped")
        return
    if not (ROOT / ".codegraph").exists():
        code, out = run([exe, "init", "."], timeout=600)
        action = "initialised"
    else:
        code, out = run([exe, "sync", "."], timeout=600)
        action = "synced"
    stat = re.search(r"([\d,]+) nodes, ([\d,]+) edges", out)
    if code == 0 and stat:
        print(f"{OK}codegraph {action} - {stat.group(1)} nodes, {stat.group(2)} edges")
    elif code == 0:
        print(f"{OK}codegraph {action}")
    else:
        print(f"{INFO}codegraph {action} skipped ({out.strip().splitlines()[-1][:80] if out.strip() else code})")


# ------------------------------------------------------------------ 4. deploy

def changed_files() -> list[str]:
    """Parse `git status --porcelain` v1.

    Format is `XY PATH` where XY is two status chars; for an unstaged-only
    modification X is a space, so `line[3:]` is off by one. Split on the first
    run of whitespace instead.
    """
    out = git("status", "--porcelain")
    files = []
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        path = parts[1]
        # renames render as "old -> new"; we care about the destination
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip().strip('"'))
    return files


def suggest_message(files: list[str]) -> str:
    """Derive a one-line commit message from what actually changed."""
    if not files:
        return "nse: session close-out"

    def any_start(*prefixes: str) -> bool:
        return any(f.replace("\\", "/").startswith(prefixes) for f in files)

    # Agent/tooling-only session: every change is local tooling, not the app.
    agent_prefixes = (".agents/", ".github/agents/", ".github/hooks/",
                      ".github/instructions/", ".github/prompts/",
                      ".github/skills/", ".context-ops/", ".vscode/",
                      ".copilotignore", ".cavemanrc", ".gitignore",
                      "package-lock.json", "CLAUDE.md")
    if files and all(f.replace("\\", "/").startswith(agent_prefixes)
                     for f in files):
        if any_start(".agents/skills/"):
            return "nse: add project skills and agent memory"
        if any_start(".agents/"):
            return "nse: update agent cache and docs"
        return "nse: update agent tooling config"

    if any_start("traders/", "setup.py", "scanner.py", "strategy_config.py"):
        return "nse: update trading methods"
    if any_start("terminal/static/"):
        return "nse: update terminal UI"
    if any_start("terminal_api.py"):
        return "nse: update API"
    if any_start("scheduler_bg.py", "daily_update.py"):
        return "nse: update scheduler and daily pipeline"
    if any_start("meta_model.py", "ml_", "pwin_cache.py"):
        return "nse: update model layer"
    if any_start("data_sources/", "ingest_", "universe"):
        return "nse: update data sources"
    if any_start(".agents/", ".github/", ".vscode/"):
        return "nse: app change plus agent tooling"
    # No known area matched; name the actual app file instead of going generic.
    app = [f for f in files
           if not f.replace("\\", "/").startswith(agent_prefixes)]
    if len(app) == 1:
        return f"nse: update {Path(app[0]).name}"
    if app:
        return f"nse: update {Path(app[0]).name} and {len(app) - 1} more"
    return "nse: session changes"


def print_deploy_blocks(files: list[str], message: str, verified: bool) -> None:
    need_restart = any(f.endswith(RESTART_TRIGGERS) or "/" not in f and f.endswith(".py")
                       for f in files if not f.startswith(".agents/"))
    need_league = any(f.replace("\\", "/").startswith(LEAGUE_TRIGGERS) for f in files)
    static_only = bool(files) and all(
        f.replace("\\", "/").startswith("terminal/static/") or f.endswith(".md")
        for f in files)

    # Push on SUBSTANTIAL change only (owner rule, 2026-10-05). Docs, cache
    # rebuilds and .agents/ state are not deploy events -- but pending work is
    # remembered, never silently dropped.
    app_files = [f for f in files
                 if not f.replace("\\", "/").startswith((".agents/", ".context-ops/"))
                 and f not in (".gitignore", ".copilotignore", ".cavemanrc",
                               "CLAUDE.md")]
    docs_only = bool(app_files) and all(
        f.endswith((".md", ".txt")) or f.startswith("docs/") for f in app_files)
    substantial = bool(app_files) and not docs_only and (
        len(app_files) > 1
        or any(f.replace("\\", "/").startswith(
            ("terminal_api.py", "db.py", "strategy_config.py", "setup.py",
             "scanner.py", "swing_live.py", "top_picks.py", "meta_model.py",
             "scheduler_bg.py", "daily_update.py", "traders/", "data_sources/",
             "universe_helper.py", "requirements")) for f in app_files))

    print()
    print("=" * 72)
    print("  UNCOMMITTED CHANGES")
    print("=" * 72)
    if not files:
        print("  (working tree clean - nothing to deploy)")
    else:
        for f in files[:25]:
            print(f"    {f}")
        if len(files) > 25:
            print(f"    ... and {len(files) - 25} more")
        print()
        if substantial:
            print("  SUBSTANTIAL change -> push + pull now.")
        elif app_files:
            print("  NOT substantial by the owner rule -> hold the deploy.")
            print("  Pending work is REMEMBERED: this change is local-only until")
            print("  a substantial change ships. Do not treat it as deployed.")
        else:
            print("  Agent/docs-only -> no deploy needed.")
    print()
    print(f"  restart nse-terminal : {'YES' if need_restart and not static_only else 'NO'}")
    print(f"  league replay needed : {'YES' if need_league else 'NO'}")
    print(f"  cache-bust ?v= bump  : {'YES (static changed)' if static_only and files else 'no'}")

    print()
    print("=" * 72)
    print("  BLOCK 1 - LAPTOP POWERSHELL  (commit + push)")
    print("=" * 72)
    print("cd C:\\Users\\Ankit\\Desktop\\nse_system")
    print("git add .")
    print(f'git commit -m "{message}"')
    print("git push")
    print("  expected: 'main -> main' plus a commit hash")

    print()
    print("=" * 72)
    print("  BLOCK 2 - SSH CONNECT")
    print("=" * 72)
    print("ssh -i C:\\Users\\Ankit\\.ssh\\nse.pem ubuntu@140.238.226.249")
    print("  expected: ubuntu@<host>:~$")

    print()
    print("=" * 72)
    print("  BLOCK 3 - VM  (pull + restart + verify)")
    print("=" * 72)
    print("cd ~/nse-system")
    print("git pull")
    if need_restart and not static_only:
        print("sudo systemctl restart nse-terminal")
        print("sleep 20")
    print("systemctl status nse-terminal --no-pager | head -5")
    print("sudo journalctl -u nse-terminal -n 300 --no-pager")
    print("  expected: 'Active: active (running)' and no new traceback")

    if need_league:
        print()
        print("=" * 72)
        print("  BLOCK 4 - VM  (REQUIRED: trader/setup/scanner code changed)")
        print("=" * 72)
        print("cd ~/nse-system")
        print("source venv/bin/activate")
        print("python trader_league.py selftest")
        print("python trader_league.py status")
        print("python trader_league.py replay --changed --background")
        print("  expected: '28/28 checks passed', then 'Code/settings changed for: ...'")

    if static_only and files:
        print()
        print("  NOTE: static-only change - no restart. On the phone, hard-refresh")
        print("        (incognito, or append ?v=2) after bumping the ?v= in index.html.")

    if not verified:
        print()
        print("  REMINDER: do not call this deployed until you have seen the")
        print("            'Active: active (running)' line from Block 3.")


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description="NSE terminal session close-out")
    ap.add_argument("--message", help="commit message (default: derived from the diff)")
    ap.add_argument("--no-codegraph", action="store_true")
    ap.add_argument("--no-deploy", action="store_true",
                    help="validate only, do not print the deploy blocks")
    args = ap.parse_args()

    problems: list[str] = []

    print("=" * 72)
    print(_ascii(f"  NSE TERMINAL - SESSION CLOSE-OUT   {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"))
    print("=" * 72)

    print("\n[1/4] Skills")
    validate_skills(problems)

    print("\n[1/4] Cache artifacts")
    validate_cache(problems)

    print("\n[1/4] Memory rules")
    validate_memory(problems)

    # Read the change set BEFORE rebuilding the cache, so the .agents/ noise the
    # rebuild creates does not pollute the deploy summary.
    files = changed_files()

    print("\n[2/4] Rebuild cache")
    rebuild_cache(problems)

    print("\n[3/4] Code index")
    resync_codegraph(not args.no_codegraph, problems)

    if not args.no_deploy:
        print("\n[4/4] Deploy")
        print_deploy_blocks(files, args.message or suggest_message(files), verified=False)

    print()
    print("=" * 72)
    if problems:
        print(f"  {len(problems)} PROBLEM(S) - fix before deploying:")
        for p in problems:
            print(f"    - {p}")
        print("=" * 72)
        return 1
    print("  ALL CHECKS PASSED - run the blocks above top to bottom.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
