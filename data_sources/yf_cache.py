"""Make yfinance's cache location provably writable before using it.

WHY THIS EXISTS (2026-10-15)
yfinance keeps a small SQLite cache (``tkr-tz.db``) holding timezone data. It
resolves that location through platformdirs. If the resolved folder cannot
actually host a SQLite database, yfinance does NOT degrade quietly: the
download dies with

    OperationalError('unable to open database file')

and returns ZERO rows without raising to the caller. Every caller in this
project therefore just sees "no data" -- the Yahoo fallback in
screener_engine, the index chain in regime.py, the ingest scripts, etc.

How this was found: on the development laptop the default location
(``%LOCALAPPDATA%\\py-yfinance``) reported as writable to ``os.access`` and
PowerShell could write plain files into it, yet SQLite could not create even a
brand-new database there. The production VM is unaffected -- its default
location works and fetched data normally. So this is a robustness guard, not a
bug fix for a broken server.

DESIGN
``ensure_yf_cache()`` probes each candidate folder by actually creating and
deleting a throwaway SQLite database, because "the directory exists" and "the
directory is writable to SQLite" are NOT the same thing on Windows. The first
candidate that passes is handed to yfinance.

The default platformdirs location is tried FIRST, so on a normal machine
(including the VM) nothing changes at all. A project-local folder is the
fallback, because it is under our control and is gitignored.

Everything is guarded: this module must never be able to take the terminal
down. If no candidate works it returns None and callers behave exactly as
before.
"""
import os
import sqlite3

_ENSURED = False
_USED = None
_DETAIL = "not checked yet"


def _project_cache_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "data", "yf-cache")


def _default_cache_dir():
    try:
        import platformdirs
        return platformdirs.user_cache_dir("py-yfinance")
    except Exception:
        return None


def _candidate_dirs():
    """Candidates in priority order: default first, so normal machines are untouched."""
    for directory in (_default_cache_dir(), _project_cache_dir(),
                      os.path.join(os.path.expanduser("~"), ".yfinance-cache")):
        if directory:
            yield directory


def sqlite_writable(directory):
    """True only if a SQLite database can really be created in `directory`.

    This is the whole point of the module: on Windows a folder can look
    writable (os.access says yes, plain files can be written) while SQLite
    still gets WinError 5. The only reliable test is to try it.
    """
    probe = os.path.join(directory, "_yf_cache_probe.db")
    try:
        os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(probe)
        conn.execute("CREATE TABLE IF NOT EXISTS probe(x)")
        conn.commit()
        conn.close()
        os.remove(probe)
        return True
    except Exception:
        for leftover in (probe, probe + "-journal", probe + "-wal"):
            try:
                if os.path.exists(leftover):
                    os.remove(leftover)
            except Exception:
                pass
        return False


def ensure_yf_cache(force=False):
    """Point yfinance at a cache folder that provably works.

    Returns the directory in use, or None if none could be found (in which case
    callers should fall back to the local database, as they already do).
    Never raises.
    """
    global _ENSURED, _USED, _DETAIL
    if _ENSURED and not force:
        return _USED
    _ENSURED = True
    _USED = None

    try:
        import yfinance as yf
    except Exception as exc:
        _DETAIL = f"yfinance unavailable: {type(exc).__name__}"
        return None

    tried = []
    for directory in _candidate_dirs():
        if not sqlite_writable(directory):
            tried.append(f"{directory} (sqlite not writable)")
            continue
        setter = getattr(yf, "set_tz_cache_location", None)
        if setter is None:
            _DETAIL = "yfinance exposes no set_tz_cache_location; left as-is"
            _USED = directory
            return _USED
        try:
            setter(directory)
        except Exception as exc:
            tried.append(f"{directory} ({type(exc).__name__})")
            continue
        _USED = directory
        _DETAIL = f"using {directory}"
        return _USED

    _DETAIL = "no usable cache dir; " + "; ".join(tried)
    return None


def cache_status():
    """Diagnostics for the source-health view and for tests."""
    return {"ensured": _ENSURED, "cache_dir": _USED, "detail": _DETAIL}
