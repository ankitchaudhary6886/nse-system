"""Fill ``fundamentals.pledge_pct`` from free, DATED exchange shareholding filings.

WHY THIS FIELD: a promoter pledging their stake is the single best free governance
red flag -- the family borrows against the company's own shares, so a price fall
triggers margin calls and forced selling exactly when the stock is already weak,
and the risk amplifies the drawdown instead of hedging it. ``fund_veto`` vetoes
above 25%, but ``fundamentals.pledge_pct`` is 100% empty here, so that rule never
fires and the gate runs blind.

WHY FILINGS, NOT THE SCANX SNAPSHOT: that snapshot is a live cross-section with no
filing date (``fundamentals_enrich`` tags it ``not_point_in_time``). A
shareholding-pattern filing is a public document with a period end and a submission
date, so a value pinned to it is replayable as of any later date. Rows carry
``shareholding:<as_of_date>`` plus the ``point_in_time`` flag; ``as_of_date`` is the
reported period end and ``raw`` keeps ``submission`` so a strict replay can add the
~2 week filing lag.

WHY THE XBRL INSIDE THE FILING: the master JSON feed carries the period end but no
pledge figure at all. Each record links an XBRL instance that does, and that instance
scopes every pledge fact by CONTEXT (``ShareholdingOfPromoterAndPromoterGroup_ContextI``),
so the promoter block can be told apart from the whole shareholding pattern. That is
the only free, dated, promoter-scoped pledge number available here.

WHY A CSV FALLBACK: NSE blocks cloud/VPS IP ranges (403 or HTML, not JSON) and
renames endpoints without notice. ``import --file`` needs no network, so the veto
gate can always be fed by hand.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, json, math, os, re, sqlite3, time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fundamentals_store

TABLE, VETO_THRESHOLD = "shareholding_pledge", 25.0
SOURCE_NSE, SOURCE_CSV = "nse", "manual_csv"
FLAGS = ["filed_shareholding", "point_in_time"]
NSE_HOME, API_ROOT = "https://www.nseindia.com/", "https://www.nseindia.com/api/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*",
           "Accept-Language": "en-US,en;q=0.9", "Referer": NSE_HOME}
# Tried in order per symbol; the first that yields a dated pledge/holding wins.
# Verified live: the first answers, the rest cover renames and gated variants.
CANDIDATES = ("corporate-share-holdings-master?index=equities&symbol={symbol}",
              "corporate-pledgedata?index=equities&symbol={symbol}",
              "corporate-share-holdings?index=equities&symbol={symbol}",
              "shareholding-pattern?index=equities&symbol={symbol}")
INSERT_SQL = (f"INSERT OR REPLACE INTO {TABLE} (symbol, as_of_date, promoter_pledge_pct, "
              "promoter_holding_pct, source, imported_at, raw) VALUES (?,?,?,?,?,?,?)")
PROMOTER_KEYS = frozenset({"prandprgrp", "promoterholding", "promoterholdingpct",
                           "promoterpct", "promotertotal", "promoter"})
DATE_KEYS = frozenset({"date", "periodenddate", "periodend", "asofdate",
                       "asperiodenddate", "quarterend", "todate", "dateofreport"})
FILED_KEYS = frozenset({"submissiondate", "broadcastdate", "filingdate"})
DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%Y/%m/%d")
FIELD_HINT = re.compile(r"pct|percent|percentage|holding|val", re.I)
PIT_NOTE = ("rows are anchored to a shareholding-pattern filing period end, a public "
            "fact, so pledge_pct is point-in-time usable (add the filing lag from "
            "raw.submission for strict replay); the ScanX snapshot is not")

# --- XBRL shareholding instances (the only source of the pledge figure) ------
SOURCE_XBRL = "nse_xbrl"
MASTER_ENDPOINT = CANDIDATES[0]  # the one endpoint that carries the xbrl link
XBRL_PLEDGE = re.compile(r"pledg|encumber", re.I)
XBRL_PERCENT = re.compile(r"percentage|percent|pct|ratio", re.I)
XBRL_SHARES = re.compile(r"shares", re.I)
XBRL_PROMOTER = re.compile(r"promoter|pppg|prandprgrp|mainppp", re.I)
XBRL_SKIP = re.compile(r"whether|notes|remarks|textblock|type", re.I)
# Denominators tried in order inside ONE context; all are that block's own share
# total (verified live: NumberOfShares == NumberOfFullyPaidUpEquityShares ==
# 1644830118 in JPPOWER's promoter context).
XBRL_TOTAL_SHARES = ("numberofshares", "numberofsharesheld", "numberofequityshares",
                     "numberoffullypaidupequityshares", "totalshares",
                     "totalnumberofshares")
# Verified live 2026-08 against JPPOWER's SHP_1691416 instance: BSE/NSE shareholding
# XBRL states every "...AsPercentageOfTotalNumberOfShares" fact as a FRACTION of the
# whole -- the promoter block says ShareholdingAsAPercentageOfTotalNumberOfShares 0.24
# where the master JSON says pr_and_prgrp 24, ShareholdingPattern_ContextI says 1 for
# 100%, and the pledge ratio 0.7299 is exactly 1200509465/1644830118 (= 72.99% of the
# promoter block). Values above 1 are already percentages (some filers ignore the
# fraction convention) and are kept as they are.
XBRL_RATIO_IS_FRACTION = True


class PledgeFetchError(RuntimeError):
    """NSE served nothing usable. Not retryable here: use ``import --file``."""


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Create the pledge table and its symbol index. Idempotent; db.py is untouched."""
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (symbol TEXT, as_of_date TEXT, "
                 "promoter_pledge_pct REAL, promoter_holding_pct REAL, source TEXT, "
                 "imported_at TEXT, raw TEXT, PRIMARY KEY(symbol, as_of_date))")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_symbol ON {TABLE}(symbol)")
    conn.commit()


def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    except sqlite3.Error:
        return []


def _clean_symbol(value: Any) -> Optional[str]:
    """Uppercase NSE ticker, or None for the junk universe_helper also drops."""
    text = str(value).strip().upper() if value is not None else ""
    return text if re.fullmatch(r"[A-Z0-9&\-\.]{1,25}", text) else None


def _number(value: Any) -> Optional[float]:
    """Finite float, or None. Bools, blanks and unparsable text are rejected."""
    if value is None or isinstance(value, bool):
        return None
    text = value.strip().replace(",", "").rstrip("%") if isinstance(value, str) else value
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_of(value: Any) -> Optional[str]:
    """NSE date text (``30-JUN-2026``, ``15-JUL-2026 18:52:47``) -> ISO date or None."""
    text = str(value).strip() if value is not None else ""
    for candidate in (text, text[:11], text[:10]):
        for fmt in DATE_FORMATS:
            try:
                return dt.datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                pass
    return None


def _pct(value: Any, key: str = "", path: str = "") -> Optional[float]:
    """Percentage in 0..100, or None when the field cannot be trusted as one.

    HEURISTIC (documented because it moves numbers): text with a literal ``%`` is
    taken at face value; a key/path naming ``ratio``/``frac`` with a value in 0..1 is
    a fraction of the whole -> *100 (XBRL filings publish ratios, their JSON twins
    publish percent); every other value in 0..100 is kept as-is, so 1.0 is 1% and
    0.73 is 0.73%; outside 0..100 is rejected, never clamped, so a share COUNT
    (NumberOfSharesEncumberedUnderPledged = 1200509465) or a mangled field cannot
    masquerade as a huge pledge rate.
    """
    number = _number(value)
    if number is None:
        return None
    if not (isinstance(value, str) and "%" in value) and 0.0 <= number <= 1.0:
        if re.search(r"ratio|frac", key + " " + path, re.I):
            number *= 100.0
    return number if 0.0 <= number <= 100.0 else None


def _walk(node: Any, path: str = "") -> Iterable[Tuple[str, str, Any]]:
    """Yield ``(key, path, scalar)`` for every leaf; dict by key, list by index."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            if isinstance(value, (dict, list)):
                yield from _walk(value, child)
            else:
                yield str(key), child, value
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, (dict, list)):
                yield from _walk(value, f"{path}[{index}]")
            else:
                yield str(index), f"{path}[{index}]", value


def _pick(record: Dict[str, Any], wanted: frozenset) -> Optional[str]:
    """First ISO date whose flattened key name is in *wanted*."""
    for key, _path, value in _walk(record):
        if re.sub(r"[^a-z0-9]", "", key.lower()) in wanted and _as_of(value):
            return _as_of(value)
    return None


def _scan(record: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Best (promoter pledge %, promoter holding %) in one filing record.

    Scores rather than guesses: a "promoter" mention beats none, an explicit alias
    (``pr_and_prgrp`` = promoter & promoter group in NSE's master feed) beats a
    generic "holding", and share COUNTS are skipped outright.
    """
    pledge, holding = (0, None), (0, None)
    for key, path, value in _walk(record):
        flat = re.sub(r"[^a-z0-9]", "", key.lower())
        number = None if "numberof" in flat or "totalshares" in flat else _pct(value, key, path)
        if number is None:
            continue
        blob = f"{path} {key}".lower()
        promoter = bool(re.search(r"promoter|pr_and_prgrp", blob))
        if re.search(r"pledg|encumber", blob):
            score = 2 if promoter else 1
            pledge = (score, number) if score > pledge[0] else pledge
        elif promoter and (flat in PROMOTER_KEYS or FIELD_HINT.search(flat)):
            score = 2 if flat in PROMOTER_KEYS else 1
            holding = (score, number) if score > holding[0] else holding
    return pledge[1], holding[1]


def _master_records(payload: Any) -> List[Any]:
    """The record list of an NSE payload: a bare list, or a dict wrapping one."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "shareholdingPattern", "records", "hldgPatt", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return [payload]


def _row_from_payload(payload: Any, symbol: str, endpoint: str) -> Optional[Dict[str, Any]]:
    """Newest dated filing in *payload* as a row; undated data is refused (not PIT)."""
    records = _master_records(payload)
    best: Optional[Tuple[str, Dict[str, Any]]] = None
    for record in records:
        if not isinstance(record, dict):
            continue
        pledge, holding = _scan(record)
        iso = _pick(record, DATE_KEYS)
        if iso and (pledge is not None or holding is not None) and (
                best is None or iso > best[0]):
            best = (iso, {"pledge": pledge, "holding": holding, "record": record})
    if best is None:
        return None
    iso, found = best
    raw = json.dumps({"endpoint": endpoint, "period_end": iso,
                      "submission": _pick(found["record"], FILED_KEYS),
                      "record": found["record"]}, default=str)[:4000]
    return {"symbol": symbol, "as_of_date": iso, "promoter_pledge_pct": found["pledge"],
            "promoter_holding_pct": found["holding"], "source": SOURCE_NSE, "raw": raw}


def _new_session(timeout: float) -> Any:
    """Browser-like session, warmed on the NSE home page for its anti-bot cookies."""
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise PledgeFetchError("requests is not installed; use `import --file`") from exc
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(NSE_HOME, timeout=timeout)
    except Exception:
        pass  # a cold session sometimes works; never fatal
    return session


def _fetch_one(session: Any, symbol: str, timeout: float) -> Dict[str, Any]:
    """First candidate endpoint that yields a dated row for *symbol*."""
    problems = []
    for template in CANDIDATES:
        name, url = template.split("?")[0], API_ROOT + template.format(symbol=symbol)
        try:
            response = session.get(url, timeout=timeout)
            if getattr(response, "status_code", 0) != 200:
                problems.append(f"{name}: HTTP {response.status_code}")
                continue
            row = _row_from_payload(response.json(), symbol, url)
        except Exception as exc:
            problems.append(f"{name}: {type(exc).__name__} (NSE serves HTML when blocking)")
            continue
        if row:
            return row
        problems.append(f"{name}: no dated pledge/promoter fields")
    raise PledgeFetchError(f"{symbol}: {'; '.join(problems)}")


def fetch_nse_shareholding(symbols: Sequence[str], session: Any = None,
                           timeout: float = 25.0,
                           sleep_seconds: float = 0.4) -> List[Dict[str, Any]]:
    """Free NSE shareholding filings -> pledge rows; one bad symbol never kills the batch.

    Raises :class:`PledgeFetchError` only when EVERY symbol failed: that is the signal
    that NSE blocks this host (cloud IP) or moved its API.
    """
    wanted: List[str] = []
    for raw in symbols or []:
        symbol = _clean_symbol(raw)
        if symbol and symbol not in wanted:
            wanted.append(symbol)
    if not wanted:
        raise PledgeFetchError("no usable symbols given (expected NSE tickers)")
    active = session if session is not None else _new_session(timeout)
    rows, failures = [], []
    for index, symbol in enumerate(wanted):
        if index and sleep_seconds:
            time.sleep(sleep_seconds)  # NSE throttles bursts with a 403
        try:
            rows.append(_fetch_one(active, symbol, timeout))
        except Exception as exc:  # one symbol must never kill the batch
            failures.append(str(exc)[:160] or symbol)
    if not rows:
        raise PledgeFetchError(
            f"NSE returned no usable shareholding data for {len(wanted)} symbol(s). NSE "
            "blocks cloud/VPS IP ranges and renames endpoints, so this is not retryable "
            "from this host. Use the offline fallback: `pledge_ingest.py import --file "
            "pledge.csv` (columns symbol,as_of_date,promoter_pledge_pct"
            f"[,promoter_holding_pct]). Last failures: {failures[:3]}")
    return rows


# ---------------------------------------------------------------------------
# XBRL: the filing's own machine-readable shareholding pattern
# ---------------------------------------------------------------------------
def _local(tag: Any) -> str:
    """Element name -> local name, whatever prefix/namespace the filer used."""
    return str(tag).rsplit("}", 1)[-1].strip()


def _norm(name: Any) -> str:
    """Lowercase alphanumerics only: ``NumberOfShares_...`` == ``numberofshares``."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _xml_bytes(document: Any) -> bytes:
    """Raw XML bytes. Bytes win: an XBRL instance declares its encoding in the prolog,
    and ElementTree refuses that declaration on a ``str``."""
    if isinstance(document, (bytes, bytearray)):
        return bytes(document).lstrip(b"\xef\xbb\xbf")
    if isinstance(document, str):
        return document.lstrip("\ufeff").encode("utf-8", "replace")
    return b""


def _response_bytes(response: Any) -> bytes:
    """XML body of a requests-like response (bytes first, ``.text`` as fallback)."""
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content):
        return _xml_bytes(content)
    return _xml_bytes(getattr(response, "text", None))


def _promoter_rank(context_id: str, member: Optional[str] = None) -> int:
    """How specifically a context means the promoter block: 4 exact block, 3 a
    promoter-group period, 2 any promoter mention, 0 everything else.

    WHY a rank and not a flag: ``NumberOfSharesEncumberedUnderPledged`` says nothing
    about whose shares -- JPPOWER files the same count in four contexts -- so the
    context alone decides. Its trust/relative contexts also mention "promoter", hence
    the graded score: only the exact block outranks them.
    """
    blob = _norm(context_id) + "|" + _norm(member)
    if "shareholdingofpromoterandpromotergroup" in blob:
        return 4
    if "mainppp" in blob:
        return 3
    return 2 if XBRL_PROMOTER.search(blob) else 0


def _xbrl_contexts(root: Any) -> Dict[str, Dict[str, Any]]:
    """contextRef id -> {period_end, member, rank}. The period end is what makes the
    numbers point-in-time; the dimension member is what makes them promoter-scoped."""
    contexts: Dict[str, Dict[str, Any]] = {}
    for element in root.iter():
        if _norm(_local(element.tag)) != "context":
            continue
        context_id = str(element.attrib.get("id") or "").strip()
        if not context_id:
            continue
        instant = end = member = None
        for child in element.iter():
            name = _norm(_local(child.tag))
            text = (child.text or "").strip()
            if name == "instant":
                instant = _as_of(text) or instant
            elif name == "enddate":
                end = _as_of(text) or end
            elif name == "explicitmember" and member is None:
                member = text or None
        contexts[context_id] = {"period_end": instant or end, "member": member,
                                "rank": _promoter_rank(context_id, member)}
    return contexts


def _xbrl_facts(root: Any) -> List[Dict[str, str]]:
    """Every numeric-carrying fact: ``{"tag", "context", "text"}``. Facts are the
    elements that point at a context, which also skips contexts/units/schemaRef."""
    facts: List[Dict[str, str]] = []
    for element in root.iter():
        context_ref = (element.attrib.get("contextRef")
                       or element.attrib.get("contextref") or "").strip()
        text = "".join(element.itertext()).strip()
        if context_ref and text:
            facts.append({"tag": _local(element.tag), "context": context_ref, "text": text})
    return facts


def _best_pledge(facts: Sequence[Dict[str, str]],
                 contexts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The best-ranked pledge PERCENT fact and pledge SHARE-COUNT fact, per context.

    Both are kept apart because they are different beasts: the percentage is a ratio
    and the count is a share count that must never be read as a percentage. The
    highest-ranked promoter context wins, and ties keep document order: JPPOWER states
    0.7299 against the promoter block and 0.1752 against the whole pattern -- the
    second is a different denominator, not a better number.
    """
    best: Dict[str, Any] = {"percent": None, "percent_context": None, "percent_rank": -1,
                            "shares": None, "shares_context": None, "shares_rank": -1}
    for fact in facts:
        name = _norm(fact["tag"])
        if "pledg" not in name or XBRL_SKIP.search(name):
            continue
        number = _number(fact["text"])
        if number is None:
            continue
        rank = int(contexts.get(fact["context"], {}).get("rank") or 0)
        if XBRL_PERCENT.search(name):
            if rank > best["percent_rank"]:
                best.update(percent=number, percent_context=fact["context"],
                            percent_rank=rank)
        elif XBRL_SHARES.search(name) and rank > best["shares_rank"]:
            best.update(shares=number, shares_context=fact["context"], shares_rank=rank)
    return best


def _context_total_shares(facts: Sequence[Dict[str, str]],
                          context_id: Optional[str]) -> Optional[float]:
    """Denominator from the SAME context as the pledge count, or None.

    Same context, never "some promoter total": mixing the two would silently divide a
    promoter-block count by the whole company's share count (JPPOWER: 72.99% of the
    promoter block vs 17.52% of all shares). No denominator -> no percentage; the count
    alone is never converted into a rate.
    """
    if not context_id:
        return None
    found: Dict[str, float] = {}
    for fact in facts:
        name = _norm(fact["tag"])
        if fact["context"] != context_id or name not in XBRL_TOTAL_SHARES:
            continue
        number = _number(fact["text"])
        if number is not None and number > 0:
            found.setdefault(name, number)
    return next((found[name] for name in XBRL_TOTAL_SHARES if name in found), None)


def _xbrl_pct(value: Any) -> Optional[float]:
    """SHP XBRL ratio fact -> percentage in 0..100, or None when it cannot be one.

    HEURISTIC (it moves numbers, so it is spelled out): these instances publish ratios
    as FRACTIONS of the whole -- verified live, JPPOWER's promoter block states
    ShareholdingAsAPercentageOfTotalNumberOfShares 0.24 where the master JSON says 24%,
    the pattern block states 1 for 100%, and the pledge ratio 0.7299 is exactly
    1200509465/1644830118 -- so a value inside 0..1 is scaled by 100 while a value
    above 1 is already percent (some filers ignore the convention). Outside 0..100 is
    REJECTED, never clamped, so a share COUNT (1200509465) can never masquerade as a
    pledge rate.
    """
    number = _number(value)
    if number is None:
        return None
    if XBRL_RATIO_IS_FRACTION and 0.0 < number <= 1.0:
        number *= 100.0
    return round(number, 4) if 0.0 <= number <= 100.0 else None


def _pledge_percentage(stated: Optional[float], shares: Optional[float],
                       total: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    """(pledge %, percentage recomputed from the count) -- the count breaks ties.

    The count over the same-context total is denominator-exact, so when the stated
    ratio disagrees with it by more than 5% the count wins; when they agree (JPPOWER:
    72.99 both ways) the stated fact is reporting the number the filer meant.
    """
    from_shares = (round(100.0 * shares / total, 4)
                   if shares is not None and total else None)
    if from_shares is not None and not 0.0 <= from_shares <= 100.0:
        from_shares = None  # a count implying 140% is a typo, not a pledge rate
    stated_pct = _xbrl_pct(stated) if stated is not None else None
    if stated_pct is not None and from_shares is not None:
        agree = abs(stated_pct - from_shares) <= max(1.0, 0.05 * from_shares)
        return (stated_pct if agree else from_shares), from_shares
    return (stated_pct if stated_pct is not None else from_shares), from_shares


def _promoter_holding(facts: Sequence[Dict[str, str]],
                      contexts: Dict[str, Dict[str, Any]]
                      ) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """(promoter holding %, context, raw fact). Promoter contexts only: the pattern
    block's own 100% is not a holding, so a non-promoter context is never accepted."""
    best: Tuple[int, Optional[float], Optional[str], Optional[float]] = (-1, None, None, None)
    for fact in facts:
        name = _norm(fact["tag"])
        if XBRL_PLEDGE.search(name) or XBRL_SKIP.search(name):
            continue
        if not XBRL_PERCENT.search(name) and "holding" not in name:
            continue
        rank = int(contexts.get(fact["context"], {}).get("rank") or 0)
        if rank <= 0 or rank <= best[0]:
            continue
        value = _xbrl_pct(fact["text"])
        if value is not None:
            best = (rank, value, fact["context"], _number(fact["text"]))
    return best[1], best[2], best[3]


def parse_shareholding_xbrl(document: Any,
                            as_of_date: Optional[str] = None
                            ) -> Optional[Dict[str, Any]]:
    """One shareholding XBRL instance -> pledge/holding facts; None when it is not XML.

    Never raises: NSE answers a blocked IP with HTML and a filer can publish a broken
    instance, so the caller decides what one bad instance costs. ABSENT facts stay
    None -- a NULL pledge means "this filing does not state one", which is NOT the
    same as a filed 0.0 -- and the raw fact values are returned untouched in ``raw`` so
    a disagreement can always be re-litigated later.
    """
    try:
        root = ET.fromstring(_xml_bytes(document))
    except ET.ParseError:
        return None
    contexts = _xbrl_contexts(root)
    facts = _xbrl_facts(root)
    if not facts and not contexts:
        return None  # well-formed but not a shareholding instance (an HTML block page)
    pledge = _best_pledge(facts, contexts)
    total = _context_total_shares(facts, pledge["shares_context"])
    percentage, from_shares = _pledge_percentage(pledge["percent"], pledge["shares"], total)
    holding, holding_context, holding_fact = _promoter_holding(facts, contexts)
    period = _as_of(as_of_date) if as_of_date else None
    for context_id in (pledge["percent_context"], pledge["shares_context"], holding_context):
        if period:
            break
        period = contexts.get(context_id or "", {}).get("period_end")
    if not period:
        period = next((row["period_end"] for row in contexts.values() if row["period_end"]),
                      None)
    rank = max(pledge["percent_rank"], pledge["shares_rank"])
    raw = {"period_end": period,
           "pledge_context": pledge["percent_context"] or pledge["shares_context"],
           "pledge_context_promoter": rank > 0,
           "pledge_pct_fact": pledge["percent"],
           "pledge_shares": pledge["shares"],
           "promoter_total_shares": total,
           "pledge_pct_from_shares": from_shares,
           "promoter_holding_context": holding_context,
           "promoter_holding_fact": holding_fact}
    return {"as_of_date": period, "promoter_pledge_pct": percentage,
            "promoter_holding_pct": holding, "raw": raw}


def _xbrl_url(record: Dict[str, Any]) -> str:
    """The record's XBRL document link, or "". ``xbrlFileSize`` is not a link."""
    for key, _path, value in _walk(record):
        if "xbrl" not in _norm(key):
            continue
        text = str(value or "").strip()
        if text.lower().startswith("http"):
            return text
    return ""


def _master_xbrl_record(records: Iterable[Any]
                        ) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """Newest master record that actually HAS an xbrl link: (url, record, period end).

    "Newest that has one", not "newest, then maybe": a revised/placeholder row without
    an instance must not throw away the latest quarter that does have one.
    """
    best: Optional[Tuple[str, Dict[str, Any], str]] = None
    for record in records:
        if not isinstance(record, dict):
            continue
        url = _xbrl_url(record)
        if not url:
            continue
        iso = _pick(record, DATE_KEYS) or ""
        if best is None or iso > best[0]:
            best = (iso, record, url)
    if best is None:
        return "", None, None
    return best[2], best[1], best[0] or None


def _master_xbrl_for(session: Any, symbol: str, timeout: float
                     ) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """First network layer: the master JSON listing, and the xbrl link inside it.

    Raises on anything that means the feed itself is unusable (HTTP != 200, HTML
    instead of JSON, a dead connection): that is the layer whose total failure is the
    "NSE blocks this host" signal, so it must not be confused with a bad instance.
    """
    response = session.get(API_ROOT + MASTER_ENDPOINT.format(symbol=symbol), timeout=timeout)
    status = getattr(response, "status_code", 0)
    if status != 200:
        raise PledgeFetchError(f"HTTP {status} (NSE serves HTML when blocking)")
    return _master_xbrl_record(_master_records(response.json()))


def _download_xbrl(session: Any, url: str, timeout: float) -> Optional[Dict[str, Any]]:
    """Second network layer: the instance itself, parsed. None when it is not XML."""
    response = session.get(url, timeout=timeout)
    status = getattr(response, "status_code", 0)
    if status != 200:
        raise PledgeFetchError(f"HTTP {status}")
    return parse_shareholding_xbrl(_response_bytes(response))


def _xbrl_row(symbol: str, as_of: Optional[str], xbrl_url: str,
              record: Optional[Dict[str, Any]], parsed: Dict[str, Any]) -> Dict[str, Any]:
    """One scanner row: pledge from the instance, provenance (url, submission, raw
    facts, context ids) in ``raw`` so a value can always be traced back to its filing."""
    record = record or {}
    details = {"endpoint": MASTER_ENDPOINT.split("?")[0], "xbrl": xbrl_url,
               "master_period_end": as_of,
               "master_date": _pick(record, DATE_KEYS),
               "submission": _pick(record, FILED_KEYS),
               "submission_date": record.get("submissionDate"),
               "broadcast_date": record.get("broadcastDate")}
    details.update(parsed["raw"])
    return {"symbol": symbol, "as_of_date": as_of or parsed["as_of_date"],
            "promoter_pledge_pct": parsed["promoter_pledge_pct"],
            "promoter_holding_pct": parsed["promoter_holding_pct"],
            "source": SOURCE_XBRL, "raw": json.dumps(details, default=str)[:4000]}


def _clean_symbols(symbols: Any, limit: Optional[int] = None) -> List[str]:
    """Uppercased, de-duplicated, order-preserving tickers (capped when *limit* set)."""
    wanted: List[str] = []
    for raw in symbols or []:
        symbol = _clean_symbol(raw)
        if symbol and symbol not in wanted:
            wanted.append(symbol)
    return wanted[:int(limit)] if limit else wanted


def fetch_nse_pledge_xbrl(symbols: Sequence[str], session: Any = None,
                          timeout: float = 25.0, sleep_seconds: float = 0.4,
                          limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Dated promoter pledge straight out of each filing's XBRL instance.

    Two network layers per symbol (master listing -> instance). Every symbol is
    isolated, so one bad symbol, a 404 archive or a broken instance only costs that
    symbol; :class:`PledgeFetchError` is raised only when layer one answers for NO
    symbol, which is the signature of an NSE block or a moved endpoint.
    """
    wanted = _clean_symbols(symbols, limit)
    if not wanted:
        raise PledgeFetchError("no usable symbols given (expected NSE tickers)")
    active = session if session is not None else _new_session(timeout)
    rows: List[Dict[str, Any]] = []
    failures: List[str] = []
    reachable = 0  # symbols whose master listing answered at all
    for index, symbol in enumerate(wanted):
        if index and sleep_seconds:
            time.sleep(sleep_seconds)  # NSE throttles bursts with a 403
        try:
            xbrl_url, record, as_of = _master_xbrl_for(active, symbol, timeout)
            reachable += 1
        except Exception as exc:  # one symbol must never kill the batch
            failures.append(f"{symbol}: master feed {type(exc).__name__}: {str(exc)[:120]}")
            continue
        if not xbrl_url:
            failures.append(f"{symbol}: master feed lists no XBRL filing")
            continue
        try:
            parsed = _download_xbrl(active, xbrl_url, timeout)
        except Exception as exc:
            failures.append(f"{symbol}: xbrl {type(exc).__name__}: {str(exc)[:120]}")
            continue
        if parsed is None or (parsed["promoter_pledge_pct"] is None
                              and parsed["promoter_holding_pct"] is None):
            failures.append(f"{symbol}: XBRL states no pledge or promoter-holding fact")
            continue
        rows.append(_xbrl_row(symbol, as_of, xbrl_url, record, parsed))
    if not reachable:
        raise PledgeFetchError(
            f"NSE's shareholding master feed answered nothing for {len(wanted)} symbol(s). "
            "NSE blocks cloud/VPS IP ranges and renames endpoints, so this is not "
            "retryable from this host. Use the offline fallback: `pledge_ingest.py "
            "import --file pledge.csv` (columns symbol,as_of_date,promoter_pledge_pct"
            f"[,promoter_holding_pct]). Last failures: {failures[:3]}")
    return rows


def _raw_json(row: Optional[Dict[str, Any]]) -> Any:
    """A row's ``raw`` back as an object, for re-embedding in a merged row."""
    if not row:
        return None
    try:
        return json.loads(row.get("raw") or "null")
    except (TypeError, ValueError):
        return str(row.get("raw"))[:400]


def _merge_rows(xbrl_rows: Sequence[Dict[str, Any]],
                json_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per (symbol, as_of_date): the XBRL keeps the pledge, the JSON feed the
    promoter holding.

    WHY this order: the JSON feed has the dated filing and the promoter holding but no
    pledge at all, while the instance has the pledge. Neither side is complete, so a
    key present in both takes the non-null value from each -- nothing is averaged and
    no 0.0 is invented for a missing side.
    """
    order: List[Tuple[str, str]] = []
    groups: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
    for row in list(xbrl_rows) + list(json_rows):
        key = (str(row.get("symbol")), str(row.get("as_of_date")))
        if key not in groups:
            order.append(key)
            groups[key] = {}
        groups[key][row.get("source")] = row
    merged: List[Dict[str, Any]] = []
    for key in order:
        group = groups[key]
        instance, feed = group.get(SOURCE_XBRL), group.get(SOURCE_NSE)
        pledge = next((row["promoter_pledge_pct"] for row in (instance, feed)
                       if row and row.get("promoter_pledge_pct") is not None), None)
        holding = next((row["promoter_holding_pct"] for row in (feed, instance)
                        if row and row.get("promoter_holding_pct") is not None), None)
        row = dict(instance or feed or {})
        row.update({"symbol": key[0], "as_of_date": key[1],
                    "promoter_pledge_pct": pledge, "promoter_holding_pct": holding,
                    "source": (SOURCE_XBRL if instance and
                               instance.get("promoter_pledge_pct") is not None
                               else (feed or row).get("source")),
                    "raw": json.dumps({"merged": True, "xbrl": _raw_json(instance),
                                       "json": _raw_json(feed)}, default=str)[:4000]})
        merged.append(row)
    return merged


def fetch_shareholding(symbols: Sequence[str], source: str = "auto", session: Any = None,
                       timeout: float = 25.0, sleep_seconds: float = 0.4,
                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """``fetch --source`` dispatch: ``json`` (old feed), ``xbrl`` (pledge), ``auto`` both.

    ``auto`` is the default because the two free feeds are complementary: the pledge
    only exists in the instance and the promoter holding is reliably in the master
    JSON, so auto runs the instance first and then fills the holding from the feed.
    Either side failing is survivable; only both failing raises.
    """
    wanted = _clean_symbols(symbols, limit)
    if not wanted:
        raise PledgeFetchError("no usable symbols given (expected NSE tickers)")
    mode = str(source or "auto").strip().lower()
    active = session if session is not None else _new_session(timeout)
    if mode.startswith("json"):
        return fetch_nse_shareholding(wanted, session=active, timeout=timeout,
                                      sleep_seconds=sleep_seconds)
    if mode.startswith("xbrl"):
        return fetch_nse_pledge_xbrl(wanted, session=active, timeout=timeout,
                                     sleep_seconds=sleep_seconds)
    problems: List[str] = []
    xbrl_rows: List[Dict[str, Any]] = []
    json_rows: List[Dict[str, Any]] = []
    try:
        xbrl_rows = fetch_nse_pledge_xbrl(wanted, session=active, timeout=timeout,
                                          sleep_seconds=sleep_seconds)
    except PledgeFetchError as exc:
        problems.append(f"xbrl: {str(exc)[:200]}")
    try:
        json_rows = fetch_nse_shareholding(wanted, session=active, timeout=timeout,
                                           sleep_seconds=sleep_seconds)
    except PledgeFetchError as exc:
        problems.append(f"json: {str(exc)[:200]}")
    if not xbrl_rows and not json_rows:
        raise PledgeFetchError(
            "NSE returned no usable shareholding data from either source. NSE blocks "
            "cloud/VPS IP ranges and renames endpoints, so this is not retryable from "
            "this host. Use the offline fallback: `pledge_ingest.py import --file "
            f"pledge.csv`. Last failures: {'; '.join(problems)}")
    return _merge_rows(xbrl_rows, json_rows)


def _csv_record(row: Dict[str, Any]) -> Optional[Tuple[Any, ...]]:
    """Validate one CSV row -> insert tuple, or None when it must be skipped."""
    clean = {str(key or "").strip().lower(): value for key, value in row.items()}
    symbol, as_of = _clean_symbol(clean.get("symbol")), _as_of(clean.get("as_of_date"))
    pledge = _number(clean.get("promoter_pledge_pct"))
    holding = _number(clean.get("promoter_holding_pct"))
    if str(clean.get("promoter_holding_pct") or "").strip() and holding is None:
        return None  # a value was supplied but is not a number
    if not symbol or not as_of or pledge is None or not 0.0 <= pledge <= 100.0:
        return None  # 140 is a typo, not a pledge rate
    if holding is not None and not 0.0 <= holding <= 100.0:
        return None
    return (symbol, as_of, pledge, holding, SOURCE_CSV,
            dt.datetime.now().isoformat(timespec="seconds"), json.dumps(clean, default=str))


def import_csv(conn: sqlite3.Connection, path: Any) -> Dict[str, Any]:
    """Upsert a manual CSV. Always available offline; bad rows are skipped, not fatal."""
    location = os.fspath(path)
    if not os.path.isfile(location):
        raise FileNotFoundError(f"no such CSV: {location}")
    ensure_tables(conn)
    seen = imported = skipped = 0
    symbols: set = set()
    with open(location, "r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            seen += 1
            record = _csv_record(row)
            if record is None:
                skipped += 1
                continue
            conn.execute(INSERT_SQL, record)
            imported += 1
            symbols.add(record[0])
    conn.commit()
    return {"rows_seen": seen, "imported": imported, "skipped": skipped,
            "symbols": sorted(symbols)}


def _coverage(conn: sqlite3.Connection) -> Dict[str, int]:
    columns = _columns(conn, "fundamentals")
    return {field: (conn.execute(f"SELECT COUNT({field}) FROM fundamentals").fetchone()[0]
                    if field in columns else 0)
            for field in ("pledge_pct", "promoter_holding")}


def apply_to_fundamentals(conn: sqlite3.Connection, overwrite: bool = False,
                          dry_run: bool = True) -> Dict[str, Any]:
    """Write each symbol's LATEST filed pledge into ``fundamentals`` via merge().

    ``pledge_pct`` is written whenever a filing supplies it: this module owns that
    field. ``promoter_holding`` is written only when fundamentals is empty for the
    symbol (or ``overwrite=True``), because a vendor's number must never be silently
    replaced just because a filing disagrees with it.
    """
    before = _coverage(conn)
    result: Dict[str, Any] = {
        "candidates": 0, "rows_touched": 0, "pledge_filled": 0, "promoter_filled": 0,
        "kept_existing": 0, "dry_run": dry_run, "coverage_after": before, "warning": None}
    fundamentals = _columns(conn, "fundamentals")
    if "pledge_pct" not in fundamentals or not _columns(conn, TABLE):
        result["warning"] = ("fundamentals.pledge_pct is absent" if "pledge_pct" not in fundamentals
                            else f"{TABLE} does not exist: run fetch or import --file first")
        return result
    latest = conn.execute(
        f"SELECT s.symbol, s.as_of_date, s.promoter_pledge_pct, s.promoter_holding_pct "
        f"FROM {TABLE} s JOIN (SELECT symbol, MAX(as_of_date) newest FROM {TABLE} "
        "GROUP BY symbol) m ON m.symbol = s.symbol AND m.newest = s.as_of_date "
        "ORDER BY s.symbol").fetchall()
    gained = {"pledge_pct": 0, "promoter_holding": 0}
    for symbol, as_of, pledge, holding in latest:
        result["candidates"] += 1
        current = conn.execute("SELECT pledge_pct, promoter_holding FROM fundamentals "
                               "WHERE symbol=?", (symbol,)).fetchone() or (None, None)
        values: Dict[str, Any] = {"symbol": symbol}
        if pledge is not None:
            values["pledge_pct"] = pledge
            result["pledge_filled"] += 1
            gained["pledge_pct"] += int(current[0] is None)
        if holding is not None and "promoter_holding" in fundamentals:
            if current[1] is None or overwrite:
                values["promoter_holding"] = holding
                result["promoter_filled"] += 1
                gained["promoter_holding"] += int(current[1] is None)
            else:
                result["kept_existing"] += 1  # never clobber a number by default
        if len(values) == 1:
            continue
        result["rows_touched"] += 1
        if not dry_run:
            fundamentals_store.merge(conn, dict(values, data_quality_flags=list(FLAGS)),
                                     source=f"shareholding:{as_of}")
    if not dry_run:
        conn.commit()
    result["coverage_after"] = {field: count + gained[field] for field, count in before.items()}
    if not result["candidates"]:
        result["warning"] = f"{TABLE} holds no rows: run fetch or import --file first"
    return result


def report(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Read-only: what the veto gate can actually see, from where, and how fresh."""
    have = bool(_columns(conn, TABLE))
    rows = symbols = 0
    latest, sources, by_source = None, {}, {}
    if have:
        rows, symbols = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT symbol) FROM {TABLE}").fetchone()
        latest = conn.execute(f"SELECT MAX(as_of_date) FROM {TABLE}").fetchone()[0]
        sources = dict(conn.execute(f"SELECT source, COUNT(*) FROM {TABLE} GROUP BY source"))
        by_source = dict(conn.execute(
            f"SELECT source, MAX(as_of_date) FROM {TABLE} GROUP BY source"))
    age = None
    try:
        age = (dt.date.today() - dt.date.fromisoformat(str(latest)[:10])).days if latest else None
    except ValueError:
        pass
    try:
        import universe_helper
        band = set(universe_helper.band_universe(conn, None))
    except Exception:  # a thin DB (no universe_broad) must not fatal a report
        band = set()
    columns = _columns(conn, "fundamentals")
    total = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0] if columns else 0
    coverage, band_cov = {}, {"total": len(band)}
    for field in ("pledge_pct", "promoter_holding"):
        if field not in columns:
            coverage[field] = {"available": False, "non_null": 0, "pct": 0.0}
            band_cov[field] = {"covered": 0, "pct": 0.0}
            continue
        non_null = conn.execute(f"SELECT COUNT({field}) FROM fundamentals").fetchone()[0]
        covered = len(band & {str(row[0] or "").strip().upper() for row in conn.execute(
            f"SELECT symbol FROM fundamentals WHERE {field} IS NOT NULL")})
        coverage[field] = {"available": True, "non_null": non_null,
                           "pct": round(100.0 * non_null / total, 1) if total else 0.0}
        band_cov[field] = {"covered": covered,
                           "pct": round(100.0 * covered / len(band), 1) if band else 0.0}
    filed = {str(row[0]): (row[1], row[2]) for row in conn.execute(
        f"SELECT symbol, as_of_date, source FROM {TABLE}")} if have else {}
    high_pledge = [{"symbol": symbol, "pledge_pct": value,
                    "as_of_date": filed.get(str(symbol), (None, None))[0],
                    "source": filed.get(str(symbol), (None, None))[1]}
                   for symbol, value in conn.execute(
                       "SELECT symbol, pledge_pct FROM fundamentals WHERE pledge_pct > ? "
                       "ORDER BY pledge_pct DESC", (VETO_THRESHOLD,))
                   ] if "pledge_pct" in columns else []
    return {
        "table": TABLE, "rows": rows, "symbols": symbols, "latest_as_of": latest,
        "sources": sources,
        "freshness": {"latest_as_of": latest, "age_days": age,
                      "by_source": {k: v for k, v in by_source.items() if k},
                      "stale": age is not None and age > 200,
                      "note": ("filings are quarterly; an age over ~200 days means the "
                               "feed stopped and pledge_pct is going stale")},
        "fundamentals_rows": total, "coverage": coverage, "band": band_cov,
        "veto_threshold": VETO_THRESHOLD, "high_pledge": high_pledge,
        "pit_valid": True, "pit_note": PIT_NOTE,
    }


def _store(conn: sqlite3.Connection, rows: Sequence[Dict[str, Any]]) -> int:
    now = dt.datetime.now().isoformat(timespec="seconds")
    conn.executemany(INSERT_SQL, [(row["symbol"], row["as_of_date"], row["promoter_pledge_pct"],
                                   row["promoter_holding_pct"], row["source"], now,
                                   row["raw"]) for row in rows])
    conn.commit()
    return len(rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="pull free NSE shareholding filings")
    fetch.add_argument("--symbols", help="comma separated NSE tickers")
    fetch.add_argument("--all", action="store_true", help="combined instead of band universe")
    fetch.add_argument("--limit", type=int, help="cap symbols processed")
    fetch.add_argument("--sleep", type=float, default=0.4, help="pause between symbols")
    fetch.add_argument("--source", choices=("auto", "xbrl", "json"), default="auto",
                       help="auto = XBRL pledge first, then the JSON feed for promoter "
                            "holding; json = old feed only; xbrl = the filing's instance")
    load = sub.add_parser("import", help="offline CSV fallback")
    load.add_argument("--file", required=True, help="CSV path")
    write = sub.add_parser("apply", help="write pledge_pct (dry run by default)")
    write.add_argument("--overwrite", action="store_true", help="also replace promoter_holding")
    write.add_argument("--apply", action="store_true", dest="write", help="write for real")
    sub.add_parser("report", help="read-only report")
    args = parser.parse_args(argv)
    import db  # lazy: only the CLI opens the real database
    conn = db.get_conn()
    try:
        if args.command == "report":
            output: Any = report(conn)
        elif args.command == "import":
            output = import_csv(conn, args.file)
        elif args.command == "apply":
            output = apply_to_fundamentals(conn, overwrite=args.overwrite,
                                           dry_run=not args.write)
        else:
            import universe_helper
            ensure_tables(conn)
            symbols = ([part.strip() for part in args.symbols.split(",") if part.strip()]
                       if args.symbols else
                       (universe_helper.combined_universe(conn) if args.all
                        else universe_helper.band_universe(conn, None)))
            symbols = symbols[:int(args.limit)] if args.limit else symbols
            # fetch writes shareholding_pledge ONLY: fundamentals stays `apply`'s job.
            rows = fetch_shareholding(symbols, source=args.source,
                                      sleep_seconds=args.sleep)
            output = {"requested": len(symbols), "source": args.source,
                      "fetched": len(rows), "stored": _store(conn, rows),
                      "with_pledge": sum(1 for row in rows
                                         if row["promoter_pledge_pct"] is not None),
                      "symbols": [row["symbol"] for row in rows]}
    finally:
        conn.close()
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
