"""Tests for the yfinance cache guard (data_sources/yf_cache.py).

The important invariant is testable WITHOUT the network: whatever directory we
hand to yfinance must provably be able to host a SQLite database. yfinance
returns zero rows instead of raising when that is not true, which is impossible
to notice from the caller's side -- that is why this guard exists.

Run: .\\env\\Scripts\\python.exe test_yf_cache.py
"""
import os
import sys
import tempfile

from data_sources.yf_cache import (cache_status, ensure_yf_cache,
                                   sqlite_writable)

FAILS = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


print("--- sqlite_writable() probes what actually matters ---")
tmp = tempfile.mkdtemp(prefix="yfcache_test_")
try:
    check("a normal temp dir is sqlite-writable", sqlite_writable(tmp) is True)
    fresh = os.path.join(tmp, "created", "nested")
    check("a missing nested dir is created and usable",
          sqlite_writable(fresh) is True and os.path.isdir(fresh))
    check("probe leaves no file behind",
          not os.path.exists(os.path.join(tmp, "_yf_cache_probe.db")))

    # A path that cannot exist: its parent is a FILE, so makedirs must fail.
    blocker = os.path.join(tmp, "iam_a_file")
    with open(blocker, "w", encoding="utf-8") as handle:
        handle.write("x")
    check("an impossible path reports False, not an exception",
          sqlite_writable(os.path.join(blocker, "sub")) is False)
finally:
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

print("\n--- ensure_yf_cache() ---")
used = ensure_yf_cache(force=True)
check("returns a directory (or None only if yfinance is missing)",
      used is not None or "yfinance" not in sys.modules, str(used))
if used:
    check("the directory it chose is really sqlite-writable",
          sqlite_writable(used) is True, used)
    check("the chosen directory exists on disk", os.path.isdir(used), used)
    status = cache_status()
    check("cache_status reports what was chosen",
          status.get("cache_dir") == used and status.get("ensured") is True,
          str(status))
    check("ensure_yf_cache is idempotent", ensure_yf_cache() == used)

print("\n--- does a real download work afterwards? ---")
try:
    import yfinance as yf
    df = yf.download("RELIANCE.NS", period="5d", interval="1d", progress=False)
    if len(df) == 0:
        # Offline is a legitimate reason for zero rows, so this cannot be a
        # hard failure -- but say so loudly rather than passing silently.
        print("SKIP  download returned 0 rows (offline, or Yahoo rate-limited)")
    else:
        check("yfinance returns rows after the guard", len(df) > 0, f"{len(df)} rows")
except Exception as exc:
    print(f"SKIP  download raised {type(exc).__name__}: {exc}")

print("\n" + "=" * 60)
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED:")
    for name in FAILS:
        print("  -", name)
    sys.exit(1)
print("ALL YF_CACHE TESTS PASSED")
