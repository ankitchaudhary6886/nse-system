"""Corporate-announcement red-flag feed for the fundamental veto (Option B).

WHY: fund_veto.py approximates risk with ratios (pledge_pct, debt/equity); the hard
evidence they proxy for -- "Resignation of Statutory Auditor", "qualified opinion /
going concern", "pledge of promoter shares", "default on NCD interest", "SEBI
penalty" -- is published by the company and mirrored by NSE with a public timestamp.
This ingests it and turns the risky subset into a dated red-flag map.

PIT: ScanX fundamentals carry NO as-of date -- valid to veto LIVE, invalid to replay
(a 2026 download cannot say what you knew in 2019). An announcement's ``announced_at``
IS the public moment, so filtering on it is backtest-eligible by construction. NEVER
overwrite ``announced_at`` with the fetch time -- that is ``fetched_at``.

SOURCE: NSE's own /api/corporate-announcements JSON endpoint. Free, no key, but NSE
BLOCKS DATACENTER/CLOUD IPs: it usually WORKS FROM A HOME LAPTOP and FAILS FROM A VM.
``AnnouncementFetchError`` says why and ``import_csv`` keeps the feed alive offline.

CLI (JSON out; db.py imported lazily): fetch --days 30 | import --file PATH |
text "subject" | list [--symbol X] [--days N] | red-flags [--days N] | report.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from typing import Any, Dict, List, Optional

FMT = "%Y-%m-%d %H:%M:%S"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))  # SQLite has no tz type
TABLE, NSE = "corporate_announcements", "https://www.nseindia.com"
API = NSE + "/api/corporate-announcements"
# Browser-like client, or NSE answers HTML/403 instead of JSON.
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
           "Accept-Language": "en-US,en;q=0.9", "Referer": NSE + "/"}
SCHEMA = """CREATE TABLE IF NOT EXISTS corporate_announcements (
  symbol TEXT, announced_at TEXT, subject TEXT, category TEXT, severity TEXT,
  flags TEXT, url TEXT, source TEXT, fetched_at TEXT, raw TEXT,
  PRIMARY KEY (symbol, announced_at, subject));
CREATE INDEX IF NOT EXISTS idx_corporate_announcements_symbol
  ON corporate_announcements(symbol, announced_at);"""

class AnnouncementFetchError(RuntimeError):
    """NSE answered, but not with usable announcements (blocked/HTML/empty)."""

RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}

# (severity, flag, regex), matched case-insensitively on subject + desc. A row's
# severity is the HIGHEST matching rule; ALL matched flags are kept. Tune ONLY here.
# ``[^.]{0,n}?`` keeps a match inside one sentence, so "SEBI (LODR) Regulations"
# cannot arm the SEBI-action rule from an unrelated clause.
RULES = [
    # HIGH: evidence a fundamental veto should never override.
    ("high", "auditor_resignation", r"resign\w*[^.]{0,40}?auditor|auditor[^.]{0,40}?resign\w*"),
    ("high", "auditor_qualification",
     r"qualified\s+opinion|qualification|emphasis\s+of\s+matter|going\s+concern"),
    ("high", "fraud", r"\bfraud|forger|embezzl|siphon|misappropriat|\bscam\b"),
    # Bare "default" is deliberate: only used for default on a payment obligation.
    ("high", "payment_default", r"\bdefault(?:ed|s)?\b"),
    ("high", "insolvency", r"insolvenc|\bnclt\b|\bcirp\b|\bibc\b|bankrupt|liquidat|winding\s+up"),
    ("high", "promoter_pledge", r"pledg|encumb"),
    # Both word orders: "SEBI penalty order" and "Order passed by SEBI".
    ("high", "sebi_action", r"sebi[^.]{0,60}?\b(?:penalt|fine|action|order|debar|ban|probe"
     r"|notice|investigat|adjudicat)\w*"
     r"|\b(?:penalt|fine|action|order|debar|ban|probe|notice)[^.]{0,60}?sebi"),
    # Needs the trading/listing context: NSE also labels filings "suspension of key
    # licenses/regulatory approvals", which is not a trading suspension.
    ("high", "trading_suspension", r"(?:suspension|suspend\w*)\s+(?:of\s+)?(?:trading|dealings|"
     r"securities|shares|listing)|\bdelist\w*|\bdebar\w*|trading\s+halt"),
    # MEDIUM: serious, but not always thesis-breaking.
    ("medium", "rating_downgrade", r"downgrad|rating[^.]{0,40}?(?:lower|negative|revised?\s+down)"),
    ("medium", "key_person_resignation", r"resign[^.]{0,60}?(?:director|chief\s+financial|\bcfo\b"
     r"|\bceo\b|company\s+secretary|\bmanager\b|\bofficer\b)"
     r"|(?:director|\bcfo\b|\bceo\b|company\s+secretary)[^.]{0,60}?resign"),
    ("medium", "regulatory_delay", r"delay[^.]{0,40}?(?:approval|clearance|regulat|permission|licen)"
     r"|(?:approval|clearance|regulator|licen\w+)[^.]{0,40}?delay|deferred"),
    ("medium", "profit_warning", r"profit\s+warning|impairment|writ(?:e|ing)?[\s-]?off|shortfall"),
    ("medium", "related_party", r"related[\s-]part"),
    # LOW: routine/administrative; stored for context, never a red flag.
    ("low", "board_meeting", r"board\s+meeting"),
    ("low", "financial_results", r"\bresults?\b|quarterly|financial\s+result"),
    ("low", "dividend", r"dividend"),
    ("low", "capital_action", r"\bbonus\b|share\s+split|sub-?division|stock\s+split|rights\s+issue"),
    ("low", "name_change", r"name\s+change|change\s+of\s+name"),
    ("low", "meeting_notice", r"\bagm\b|annual\s+general|\begm\b|postal\s+ballot"),
]

SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9&\-\.]{0,19}$")
DT_FORMATS = ("%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
              "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d")
BLOCKED = ("NSE announcements API blocked: it returned {what}. The endpoint is free, but "
           "NSE refuses datacenter/cloud IPs (works from a home laptop, usually fails from a "
           "VM). Retry from a residential IP or use the CSV fallback: python announcements.py "
           "import --file FILE (columns: symbol, announced_at, subject, category, url)")

def _text(value: Any) -> str:
    """Coerce anything to str without ever raising (None/bytes/objects)."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return "" if value is None else (value if isinstance(value, str) else str(value))

def _parse_dt(value: Any) -> Optional[str]:
    """Normalise NSE's date spellings to 'YYYY-MM-DD HH:MM:SS' (or None)."""
    if isinstance(value, (dt.datetime, dt.date)):
        moment = value if isinstance(value, dt.datetime) else dt.datetime(
            value.year, value.month, value.day)
        return moment.strftime(FMT)
    text = re.sub(r"\.\d+$", "", re.sub(
        r"\s+", " ", _text(value).replace("IST", " ").replace("Z", " "))).strip()
    for fmt in DT_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).strftime(FMT) if text else None
        except ValueError:
            continue
    return None

def _to_date(value: Any) -> Optional[dt.date]:
    stamp = _parse_dt(value)
    return dt.datetime.strptime(stamp, FMT).date() if stamp else None

def _cutoff(days: Any) -> Optional[str]:
    """Window start, or None for all history (days <= 0 / unparseable)."""
    try:
        days = int(days)
    except (TypeError, ValueError):
        return None
    return None if days <= 0 else (dt.datetime.now(IST) - dt.timedelta(days=days)).strftime(FMT)

def _flag_list(value: Any) -> List[str]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return []
    return [item for item in map(_text, parsed) if item] if isinstance(parsed, (list, tuple)) else []

def ensure_tables(conn) -> None:
    """Create the announcement table + index. Idempotent; safe on every call."""
    conn.executescript(SCHEMA)
    # Keep sorts/aggregates in RAM: on a big table SQLite would otherwise spill to a
    # temp FILE, and a locked-down temp dir fails "unable to open database file".
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.commit()

def classify(subject: Any, desc: Any = "") -> Dict[str, Any]:
    """Keyword verdict for one announcement: {severity, flags}; never raises."""
    text, severity, flags = _text(subject) + "\n" + _text(desc), "none", []
    for level, flag, pattern in RULES:
        if re.search(pattern, text, re.I) and flag not in flags:
            flags.append(flag)
            severity = level if RANK[level] > RANK[severity] else severity
    return {"severity": severity, "flags": flags}

def _normalize_row(row: Any) -> Optional[Dict[str, Any]]:
    """Map one NSE row to our shape; None for a weird row, never raises."""
    if not isinstance(row, dict):
        return None
    try:
        symbol = re.sub(r"[-_](?:EQ|BE|BZ)$", "", _text(row.get("symbol") or row.get("sym"))
                        .upper().split()[0])
        subject = _text(row.get("subject") or row.get("desc") or row.get("sm_name")).strip()
        when = _parse_dt(row.get("an_dt") or row.get("sort_date") or row.get("exchdisstime"))
        url = _text(row.get("attchmntFile") or row.get("attachment") or row.get("url")).strip()
        if not symbol or not subject or not when:
            return None  # unusable row: skip it, never kill the batch
        url = "https:" + url if url.startswith("//") else (NSE + url if url.startswith("/") else url)
        return {"symbol": symbol, "announced_at": when, "subject": subject, "url": url,
                "source": "nse_api", "raw": json.dumps(row, default=str),
                "category": _text(row.get("category") or row.get("subCategory")).strip()}
    except Exception:
        return None

def fetch_nse(from_date: Any, to_date: Any, session: Any = None,
              timeout: int = 25) -> List[Dict[str, Any]]:
    """Pull NSE corporate announcements for a date range. Free, no key.

    Warms a browser-like session on nseindia.com so the WAF issues cookies, then GETs
    the JSON API with index=equities and DD-MM-YYYY dates. NSE BLOCKS DATACENTER/CLOUD
    IPs: this normally WORKS FROM A HOME LAPTOP and FAILS FROM A VM -> raises
    AnnouncementFetchError, writes nothing, which is why import_csv exists.
    """
    import requests  # lazy: importing this module stays free (GOLDEN RULE 7)
    start, end = _to_date(from_date), _to_date(to_date)
    if start is None or end is None:
        raise AnnouncementFetchError(f"bad date range {from_date!r}..{to_date!r}; use YYYY-MM-DD")
    own, sess = session is None, requests.Session() if session is None else session
    try:
        try:
            sess.get(NSE, headers=HEADERS, timeout=timeout)  # cookie warm-up
        except Exception:
            pass  # best-effort; the API call reports the real error
        resp = sess.get(API, headers=HEADERS, timeout=timeout, params={
            "index": "equities", "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y")})
    finally:
        if own:
            sess.close()
    status, body = getattr(resp, "status_code", 200), _text(getattr(resp, "text", ""))
    header = getattr(resp, "headers", None) or {}
    ctype = _text(header.get("Content-Type") if hasattr(header, "get") else "").lower()
    if status in (401, 403, 429):
        raise AnnouncementFetchError(BLOCKED.format(what=f"HTTP {status}"))
    if not body.strip() or body.lstrip()[:1] == "<" or "html" in ctype:
        raise AnnouncementFetchError(BLOCKED.format(what="an empty or HTML body"))
    try:
        payload = resp.json()
    except Exception as exc:
        raise AnnouncementFetchError(BLOCKED.format(what="a non-JSON body")) from exc
    rows = payload if isinstance(payload, list) else (
        payload.get("data") if isinstance(payload, dict) else None)
    if not isinstance(rows, list) or not rows:
        raise AnnouncementFetchError(BLOCKED.format(what="an empty JSON list"))
    items = [item for item in map(_normalize_row, rows) if item]
    if not items:
        raise AnnouncementFetchError(f"NSE returned {len(rows)} rows but none usable (schema "
                                     "drift); inspect a raw row, then: python announcements.py "
                                     "import --file FILE")
    return items

def store(conn, items: Any) -> Dict[str, Any]:
    """Insert-or-ignore (PK dedupe), classifying each. Returns {seen, inserted,
    skipped, by_severity}; by_severity counts only rows actually inserted."""
    ensure_tables(conn)
    fetched_at = dt.datetime.now(IST).strftime(FMT)
    seen = inserted = skipped = 0
    by_severity = {level: 0 for level in RANK}
    for item in (items if isinstance(items, (list, tuple)) else []):
        seen += 1
        if not isinstance(item, dict):
            skipped += 1; continue
        symbol = _text(item.get("symbol")).upper().strip()
        when = _parse_dt(item.get("announced_at"))
        subject = _text(item.get("subject")).strip()
        category = _text(item.get("category")).strip()
        if not symbol or not when or not subject:
            skipped += 1; continue
        verdict = classify(subject, category)
        # Column order matches SCHEMA exactly (we own the table).
        cursor = conn.execute(f"INSERT OR IGNORE INTO {TABLE} VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (symbol, when, subject, category, verdict["severity"],
                               json.dumps(verdict["flags"]), _text(item.get("url")).strip(),
                               _text(item.get("source")).strip() or "nse_api", fetched_at,
                               _text(item.get("raw"))))
        inserted, skipped = inserted + bool(cursor.rowcount), skipped + (not cursor.rowcount)
        by_severity[verdict["severity"]] += bool(cursor.rowcount)
    conn.commit()
    return {"seen": seen, "inserted": inserted, "skipped": skipped, "by_severity": by_severity}

def import_csv(conn, path: str) -> Dict[str, Any]:
    """Offline fallback: CSV (symbol, announced_at, subject, category, url) through the
    same store path. Any severity column in the file is IGNORED -- severity is always
    recomputed so flags stay consistent with RULES. Bad symbol/date/subject makes a row
    invalid (counted, never fatal). Re-importing the same file is idempotent."""
    ensure_tables(conn)
    items, rows_read, invalid = [], 0, 0
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows_read += 1
            low = {_text(key).strip().lower(): val for key, val in row.items()}
            symbol = _text(low.get("symbol")).upper().strip()
            when = _parse_dt(low.get("announced_at") or low.get("date"))
            subject = _text(low.get("subject") or low.get("desc")).strip()
            if not SYMBOL_RE.match(symbol) or not when or not subject:
                invalid += 1; continue
            items.append({"symbol": symbol, "announced_at": when, "subject": subject,
                          "category": _text(low.get("category")).strip(),
                          "url": _text(low.get("url")).strip(), "source": "manual_csv"})
    result = store(conn, items)
    result.update({"rows_read": rows_read, "invalid": invalid})
    return result

def _rows(conn, days: int = 365, symbol: Optional[str] = None,
          limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Stored announcements inside the announced_at window, newest first."""
    keys = ("symbol", "announced_at", "subject", "category", "severity", "flags",
            "url", "source", "fetched_at")
    sql = f"SELECT {', '.join(keys)} FROM {TABLE} WHERE announced_at >= ?"
    args: List[Any] = [_cutoff(days) or "0000"]  # "0000" sorts below any ISO date
    if symbol:
        sql += " AND symbol = ?"; args.append(symbol.upper().strip())
    sql += " ORDER BY announced_at DESC" + (" LIMIT ?" if limit else "")
    if limit:
        args.append(int(limit))
    return [dict(zip(keys, row), flags=_flag_list(row[5])) for row in conn.execute(sql, args)]

def red_flags(conn, days: int = 365,
              severities: Any = ("high", "medium")) -> Dict[str, Any]:
    """READ-ONLY map symbol -> {announcements, latest, flags, severity}.

    Only symbols with a stored flag inside the window AND in ``severities``; this is
    the shape fund_veto consumes. The window is announced_at (point-in-time), never
    fetched_at; days <= 0 means all history. Writes no announcement rows.
    """
    ensure_tables(conn)
    wanted = [level for level in (severities or ()) if level in RANK] or ["high", "medium"]
    out: Dict[str, Any] = {}
    for row in _rows(conn, days):
        if row["severity"] not in wanted:
            continue
        entry = out.setdefault(_text(row["symbol"]), {
            "announcements": 0, "flags": [], "latest": row["announced_at"],
            "severity": row["severity"]})
        entry["announcements"] += 1
        entry["latest"] = max(_text(entry["latest"]), _text(row["announced_at"]))
        entry["severity"] = max((entry["severity"], row["severity"]), key=RANK.get)
        entry["flags"] += [flag for flag in row["flags"] if flag not in entry["flags"]]
    return out

def report(conn, days: int = 365) -> Dict[str, Any]:
    """Counts by severity/flag, latest fetch, symbols covered, high sample."""
    ensure_tables(conn)
    rows = _rows(conn, days)
    by_severity = {level: 0 for level in RANK}
    by_severity.update(Counter(row["severity"] for row in rows))
    by_flag = dict(sorted(Counter(flag for row in rows for flag in row["flags"]).items(),
                          key=lambda pair: -pair[1]))
    fetched = [_text(row["fetched_at"]) for row in rows if _text(row["fetched_at"])]
    return {"window_days": days, "cutoff": _cutoff(days), "total": len(rows),
            "by_severity": by_severity, "by_flag": by_flag,
            "latest_fetch": max(fetched) if fetched else None,
            "symbols": len({_text(row["symbol"]) for row in rows}),
            "high_risk_sample": [
                {"symbol": _text(row["symbol"]), "announced_at": row["announced_at"],
                 "subject": _text(row["subject"])[:200], "flags": row["flags"]}
                for row in rows if row["severity"] == "high"][:10]}

def _parser() -> argparse.ArgumentParser:
    """argparse wiring: one subcommand per documented CLI verb."""
    parser = argparse.ArgumentParser(prog="announcements.py",
                                     description="NSE announcements -> dated red flags")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "import", "text", "list", "red-flags", "report"):
        sub.add_parser(name).add_argument("--days", type=int, default=365)
    sub.choices["fetch"].set_defaults(days=30)
    sub.choices["list"].add_argument("--symbol")
    sub.choices["text"].add_argument("text")
    sub.choices["import"].add_argument("--file", required=True)
    return parser

def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "text":  # pure: no DB, no network, no lazy import
        print(json.dumps(classify(args.text), indent=2))
        return 0
    import db  # lazy: only DB commands may touch data/app.db (GOLDEN RULE 7)
    conn = db.get_conn()
    try:
        if args.cmd == "import":
            out = import_csv(conn, args.file)
        elif args.cmd == "fetch":
            end = dt.datetime.now(IST).date()
            try:
                out = dict(store(conn, fetch_nse(end - dt.timedelta(days=max(1, args.days)), end)),
                           ok=True)
            except AnnouncementFetchError as exc:
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
                return 1
        elif args.cmd == "list":
            ensure_tables(conn)
            rows = _rows(conn, args.days, args.symbol, limit=200)
            out = {"count": len(rows), "rows": rows}
        elif args.cmd == "red-flags":
            out = red_flags(conn, days=args.days)
        else:
            out = report(conn, days=args.days)
        print(json.dumps(out, indent=2, default=str))
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
