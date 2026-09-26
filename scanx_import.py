"""Import a dated ScanX fundamentals export using an NSE security master.

The import is a current snapshot, not point-in-time historical data.
Unmatched names are deliberately left out instead of fuzzy-matched.
"""
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

import db


ALIASES = {
    "LIC of India": "LICI",
    "Sun Pharmaceutical": "SUNPHARMA",
    "Adani Ports & SEZ": "ADANIPORTS",
    "Kotak Bank": "KOTAKBANK",
    "Avenue Supermarts DMart": "DMART",
    "TVS Motors": "TVSMOTOR",
    "Cholamandalam Investment": "CHOLAFIN",
    "Apollo Hospitals": "APOLLOHOSP",
    "Bajaj Holdings & Investments": "BAJAJHLDNG",
    "Zydus Life Science": "ZYDUSLIFE",
    "Groww": "GROWW",
    "IRFC": "IRFC",
    "HDFC AMC": "HDFCAMC",
    "Nykaa": "NYKAA",
    "MCX": "MCX",
    "Nippon Life India AMC": "NAM-INDIA",
    "NALCO": "NATIONALUM",
    "GIC of India": "GICRE",
    "SBI Cards": "SBICARD",
    "Berger Paints": "BERGEPAINT",
    "Fertilisers & Chemical Travancore": "FACT",
    "Tube Investment": "TIINDIA",
    "Authum Inv & Infr": "AIIL",
    "M&M Financial Services": "M&MFIN",
    "IRCTC": "IRCTC",
    "HUDCO": "HUDCO",
    "Syrma SGS": "SYRMA",
    "Star Health Insurance": "STARHEALTH",
    "IREDA": "IREDA",
    "Schneider Electric Infra": "SCHNEIDER",
    "Mangalore Refinery & Petroleum": "MRPL",
    "CDSL": "CDSL",
    "ZF Commercial": "ZFCVINDIA",
    "Garden Reach Shipbuilders": "GRSE",
    "EIH Hotels": "EIHOTEL",
    "Triveni Turbines": "TRITURBINE",
    "CAMS": "CAMS",
    "Deepak Fertilisers & Petrochemicals": "DEEPAKFERT",
    "Chambal Fertilisers & Chemicals": "CHAMBLFERT",
    "DCM Shriram Consolidated": "DCMSHRIRAM",
    "Mamaearth": "HONASA",
    "Crompton Greaves": "CROMPTON",
    "Akums Drugs & Pharma": "AKUMS",
    "Whirlpool": "WHIRLPOOL",
    "UTI AMC": "UTIAMC",
    "Yatharth Hospital": "YATHARTH",
    "Paras Defence Space Tech": "PARAS",
    "RateGain Travel": "RATEGAIN",
    "Firstcry (Brainbees Solutions)": "FIRSTCRY",
    "Gujarat Narmada Valley Fert & Chem": "GNFC",
    "Jupiter Life Line Hospital": "JLHL",
    "Banco Products": "BANCOINDIA",
    "Axiscades Engineering Technologies": "AXISCADES",
    "Zee Entertainment": "ZEEL",
    "Jyothy Laboratories": "JYOTHYLAB",
    "Le Travenues Technology (IXIGO)": "IXIGO",
    "Mrs. Bectors Food": "BECTORFOOD",
    "Restaurant Brand Asia (Burger King)": "RBA",
    "Advanced Enzyme Tech": "ADVENZYMES",
}


def _norm(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    tokens = re.findall(r"[a-z0-9]+", text.replace("&", " and "))
    while tokens and tokens[0] == "the":
        tokens.pop(0)
    while tokens and tokens[-1] in {
            "limited", "ltd", "incorporated", "inc", "corporation",
            "corp", "company", "co", "india"}:
        tokens.pop()
    return "".join(tokens)


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no CSV header")
        return [{str(k).strip(): (v or "").strip()
                 for k, v in row.items()} for row in reader]


def _master_index(path):
    rows = _read_csv(path)
    by_name = defaultdict(dict)
    by_symbol = {}
    for row in rows:
        symbol = row.get("SYMBOL", "").upper()
        series = row.get("SERIES", "").upper()
        if not symbol or series not in {"EQ", "BE", "BZ"}:
            continue
        record = {
            "symbol": symbol,
            "isin": row.get("ISIN NUMBER", ""),
            "company_name": row.get("NAME OF COMPANY", ""),
        }
        by_name[_norm(record["company_name"])][symbol] = record
        by_symbol[symbol] = record
    return by_name, by_symbol


def _resolve(rows, by_name, by_symbol):
    mapped, unmatched = [], []
    for row in rows:
        name = row.get("Name", "")
        override = ALIASES.get(name)
        if override:
            security = by_symbol.get(override)
            method = "curated_alias"
            if security is None:
                raise ValueError(
                    f"Alias {name!r} points to missing NSE EQ symbol "
                    f"{override!r}")
        else:
            candidates = by_name.get(_norm(name), {})
            if len(candidates) != 1:
                unmatched.append(name)
                continue
            security = next(iter(candidates.values()))
            method = "normalized_exact"
        mapped.append({
            "scanx_name": name,
            "symbol": security["symbol"],
            "isin": security["isin"],
            "company_name": security["company_name"],
            "match_method": method,
            "row": row,
        })

    seen = set()
    for item in mapped:
        if item["symbol"] in seen:
            raise ValueError(
                f"Multiple ScanX rows map to {item['symbol']}; "
                "refusing an ambiguous import")
        seen.add(item["symbol"])
    return mapped, unmatched


def _number(row, *names):
    for name in names:
        value = row.get(name, "")
        if not value or value.strip().lower() in {"-", "--", "na", "n/a",
                                                   "null", "none"}:
            continue
        value = value.replace(",", "").replace("%", "").strip()
        try:
            return float(value)
        except ValueError:
            continue
    return None


def _snapshot_values(item, as_of):
    row = item["row"]
    cfo = _number(row, "Operating Cash Flow")
    return {
        "as_of_date": as_of,
        "symbol": item["symbol"],
        "isin": item["isin"],
        "scanx_name": item["scanx_name"],
        "company_name": item["company_name"],
        "sector": row.get("Industry") or None,
        "current_price": _number(row, "Close Price", "Price"),
        "market_cap_cr": _number(row, "Market Cap (Cr.)"),
        "pe": _number(row, "P/E Ratio"),
        "pb": _number(row, "PB Ratio"),
        "roe": _number(row, "Return on Equity", "Average ROE 3Years"),
        "roce": _number(row, "Return on Capital Employed"),
        "debt_to_equity": _number(row, "Debt to Equity"),
        "operating_margin": _number(row, "OPM"),
        "net_profit_margin": _number(row, "Net Profit Margin"),
        "promoter_holding": _number(row, "Promoter Holding %"),
        "fii_holding": _number(row, "FII Holding"),
        "dii_holding": _number(row, "DII Holding"),
        "dividend_yield": _number(row, "Dividend Yield"),
        "operating_cash_flow": cfo,
        "cfo_positive": None if cfo is None else int(cfo > 0),
        "raw_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
        "match_method": item["match_method"],
    }


def _backup(path):
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.pre-scanx-{stamp}.bak")
    source_conn = sqlite3.connect(str(path))
    backup_conn = sqlite3.connect(str(target))
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()
    return target


def _apply(path, snapshots, source_file):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(fundamentals)")}
        if not cols:
            raise RuntimeError("fundamentals table is missing")
        imported_at = dt.datetime.now().isoformat(timespec="seconds")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scanx_fundamentals_snapshots (
                as_of_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                isin TEXT,
                scanx_name TEXT,
                company_name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap_cr REAL,
                pe REAL,
                pb REAL,
                roe REAL,
                roce REAL,
                debt_to_equity REAL,
                operating_margin REAL,
                net_profit_margin REAL,
                promoter_holding REAL,
                fii_holding REAL,
                dii_holding REAL,
                dividend_yield REAL,
                operating_cash_flow REAL,
                cfo_positive INTEGER,
                raw_json TEXT NOT NULL,
                match_method TEXT NOT NULL,
                source_file TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                PRIMARY KEY (as_of_date, symbol)
            )
        """)
        conn.execute("BEGIN")
        snapshot_cols = [
            "as_of_date", "symbol", "isin", "scanx_name", "company_name",
            "sector", "current_price", "market_cap_cr", "pe", "pb", "roe",
            "roce", "debt_to_equity", "operating_margin",
            "net_profit_margin", "promoter_holding", "fii_holding",
            "dii_holding", "dividend_yield", "operating_cash_flow",
            "cfo_positive", "raw_json", "match_method", "source_file",
            "imported_at",
        ]
        existing_symbols = {
            row[0] for row in conn.execute("SELECT symbol FROM fundamentals")
        }
        merged = 0
        for snapshot in snapshots:
            values = dict(snapshot)
            values.update(source_file=Path(source_file).name,
                          imported_at=imported_at)
            conn.execute(
                "INSERT INTO scanx_fundamentals_snapshots "
                f"({','.join(snapshot_cols)}) VALUES "
                f"({','.join('?' for _ in snapshot_cols)}) "
                "ON CONFLICT(as_of_date,symbol) DO UPDATE SET " +
                ",".join(f"{key}=excluded.{key}" for key in snapshot_cols
                         if key not in ("as_of_date", "symbol")),
                [values.get(key) for key in snapshot_cols])

            fundamental = {
                "symbol": snapshot["symbol"],
                "name": snapshot["company_name"],
                "sector": snapshot["sector"],
                "current_price": snapshot["current_price"],
                "market_cap_cr": snapshot["market_cap_cr"],
                "pe": snapshot["pe"],
                "pb": snapshot["pb"],
                "roe": snapshot["roe"],
                "roce": snapshot["roce"],
                "debt_to_equity": snapshot["debt_to_equity"],
                "operating_margin": snapshot["operating_margin"],
                "net_profit_margin": snapshot["net_profit_margin"],
                "promoter_holding": snapshot["promoter_holding"],
                "fii_holding": snapshot["fii_holding"],
                "dividend_yield": snapshot["dividend_yield"],
                "cfo_positive": snapshot["cfo_positive"],
                "uploaded_at": f"scanx:{imported_at}",
            }
            if "data_source" in cols:
                fundamental["data_source"] = "scanx"
            if snapshot["symbol"] not in existing_symbols:
                continue
            fundamental = {key: value for key, value in fundamental.items()
                           if key in cols and key != "symbol"}
            assignments = ",".join(
                f"{key}=COALESCE(?,{key})" for key in fundamental)
            conn.execute(
                f"UPDATE fundamentals SET {assignments} WHERE symbol=?",
                [*fundamental.values(), snapshot["symbol"]])
            merged += 1
        conn.commit()
        return imported_at, merged
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="ScanX export CSV")
    parser.add_argument("--master", default="data/incoming/nse_equity_master.csv",
                        help="NSE EQUITY_L.csv security master")
    parser.add_argument("--as-of", required=True,
                        help="Snapshot date YYYY-MM-DD")
    parser.add_argument("--db", default=str(db.DB_PATH),
                        help="Target SQLite database")
    parser.add_argument("--apply", action="store_true",
                        help="Back up the database, then import")
    args = parser.parse_args(argv)
    as_of = dt.date.fromisoformat(args.as_of).isoformat()
    source = Path(args.csv)
    master = Path(args.master)
    if not source.is_file() or not master.is_file():
        raise FileNotFoundError("ScanX CSV or NSE security master not found")
    rows = _read_csv(source)
    by_name, by_symbol = _master_index(master)
    mapped, unmatched = _resolve(rows, by_name, by_symbol)
    if not mapped:
        raise RuntimeError("No ScanX company names could be mapped")
    snapshots = [_snapshot_values(item, as_of) for item in mapped]
    if args.apply:
        target = Path(args.db).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"Target database does not exist: {target}")
        backup = _backup(target)
        imported_at, merged = _apply(target, snapshots, source)
        print(f"Imported {len(snapshots)} dated ScanX snapshots "
              f"({as_of}; {imported_at}) into {target}")
        print(f"Updated {merged} existing fundamentals rows; new rows were "
              "not added to the active trading universe.")
        print(f"Pre-import database backup: {backup}")
    else:
        print(f"Dry run: {len(snapshots)} unique mapped rows; "
              f"{len(unmatched)} unmatched; snapshot date {as_of}")
    if unmatched:
        print("Unmatched company names (not imported):")
        for name in unmatched:
            print(f"  {name}")
    print("Snapshot records preserve source fields and source names. "
          "Compatible fields are merged only for symbols already in "
          "fundamentals; "
          "quarterly/yearly metrics are not relabeled as 3-year growth.")


if __name__ == "__main__":
    main()
