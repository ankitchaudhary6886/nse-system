"""Small, non-destructive storage helper for fundamentals imports.

Importers deliberately use this module instead of row replacement.  A source
usually supplies only a subset of a fundamentals row; a null in that subset
must not erase a value supplied by another source.
"""
import datetime as _dt
import json
import math


META_COLUMNS = {
    "symbol", "data_source", "uploaded_at", "field_sources",
    "field_updated_at", "data_quality_flags",
}


def _present(value):
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _json_object(value):
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _columns(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(fundamentals)")}


def merge(conn, values, source=None, observed_at=None):
    """Merge non-null fields in *values* into one fundamentals row.

    ``field_sources`` and ``field_updated_at`` are intentionally per-field;
    the row-level ``data_source``/``uploaded_at`` only describe the latest
    import event and do not make preserved fields look freshly observed.
    Returns the fields changed by this import.
    """
    if not values or not _present(values.get("symbol")):
        raise ValueError("fundamentals merge requires a symbol")
    cols = _columns(conn)
    symbol = values["symbol"]
    now = observed_at or _dt.datetime.now().isoformat()
    source = source or values.get("data_source") or "unknown"
    incoming = {
        key: value for key, value in values.items()
        if key in cols and key not in META_COLUMNS and _present(value)
    }
    # Quality flags are additive and are not a replacement for field data.
    flags = values.get("data_quality_flags")
    existing = conn.execute(
        "SELECT * FROM fundamentals WHERE symbol=?", (symbol,)).fetchone()
    names = [row[1] for row in conn.execute("PRAGMA table_info(fundamentals)")]
    old = dict(zip(names, existing)) if existing else {}
    field_sources = _json_object(old.get("field_sources"))
    field_updated = _json_object(old.get("field_updated_at"))
    changed = []
    for key in incoming:
        field_sources[key] = source
        field_updated[key] = now
        changed.append(key)
    old_flags = set(_json_object(old.get("data_quality_flags")).get("flags", []))
    if not old_flags:
        old_flags = set(str(old.get("data_quality_flags") or "").split(",")) - {""}
    if flags:
        if isinstance(flags, (list, tuple, set)):
            old_flags.update(str(flag) for flag in flags if flag)
        else:
            old_flags.update(str(flags).split(","))

    metadata = {}
    if "data_source" in cols:
        metadata["data_source"] = source
    if "uploaded_at" in cols:
        metadata["uploaded_at"] = now
    if "field_sources" in cols:
        metadata["field_sources"] = json.dumps(field_sources, sort_keys=True)
    if "field_updated_at" in cols:
        metadata["field_updated_at"] = json.dumps(field_updated, sort_keys=True)
    if "data_quality_flags" in cols and old_flags:
        metadata["data_quality_flags"] = json.dumps(
            {"flags": sorted(old_flags)}, sort_keys=True)

    if existing is None:
        row = {"symbol": symbol}
        row.update(incoming)
        row.update(metadata)
        keys = [key for key in names if key in row]
        placeholders = ",".join("?" for _ in keys)
        conn.execute(
            "INSERT INTO fundamentals ({}) VALUES ({})".format(
                ",".join(keys), placeholders), [row[key] for key in keys])
    else:
        updates = dict(incoming)
        updates.update(metadata)
        if updates:
            assignments = ",".join("{}=?".format(key) for key in updates)
            conn.execute(
                "UPDATE fundamentals SET {} WHERE symbol=?".format(assignments),
                list(updates.values()) + [symbol])
    return changed


def integrity_report(conn):
    """Return legacy rows needing review without rewriting their values.

    Historical data is never silently reclassified.  The report flags rows
    that predate field provenance and the known TradingView FCF/CFO proxy.
    """
    cols = _columns(conn)
    if "field_sources" not in cols:
        return {"remediation_needed": True, "rows": [],
                "reason": "field provenance migration is not available"}
    rows = []
    for row in conn.execute(
            "SELECT symbol,data_source,cfo_positive,fcf_fy,field_sources "
            "FROM fundamentals"):
        sources = _json_object(row[4])
        reasons = []
        if not sources:
            reasons.append("legacy row has no field provenance")
        if row[1] == "tradingview" and row[2] is not None:
            reasons.append("cfo_positive may be an historical FCF sign proxy")
        if reasons:
            rows.append({"symbol": row[0], "reasons": reasons})
    return {"remediation_needed": bool(rows), "rows": rows}
