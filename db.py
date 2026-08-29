import sqlite3
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
  symbol TEXT PRIMARY KEY, name TEXT, sector TEXT,
  active INTEGER DEFAULT 1, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS prices_daily (
  symbol TEXT, date TEXT,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS price_meta (
  symbol TEXT PRIMARY KEY, last_date TEXT, rows INTEGER, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS fundamentals (
  symbol TEXT PRIMARY KEY, name TEXT, sector TEXT,
  current_price REAL, market_cap_cr REAL, pe REAL, pb REAL,
  roe REAL, roce REAL, debt_to_equity REAL, interest_coverage REAL,
  operating_margin REAL, net_profit_margin REAL,
  sales_growth_3y REAL, profit_growth_3y REAL,
  promoter_holding REAL, pledge_pct REAL, fii_holding REAL,
  dividend_yield REAL, cfo_positive INTEGER, uploaded_at TEXT
);
CREATE TABLE IF NOT EXISTS scan_results (
  scan_date TEXT, symbol TEXT, passed INTEGER,
  fundamental_score REAL, ml_score REAL, risk_flags TEXT, status TEXT,
  PRIMARY KEY (scan_date, symbol)
);
CREATE TABLE IF NOT EXISTS scan_reasons (
  scan_date TEXT, symbol TEXT, rule_name TEXT, passed INTEGER,
  actual_value REAL, expected_text TEXT, reason_text TEXT
);
CREATE TABLE IF NOT EXISTS pipeline (
  symbol TEXT PRIMARY KEY, status TEXT, added_date TEXT,
  updated_date TEXT, reason TEXT, notes TEXT, review_date TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sentiment_results (
  symbol TEXT, created_at TEXT, headline_count INTEGER,
  positive INTEGER, neutral INTEGER, negative INTEGER,
  sentiment_score REAL, major_negative TEXT
);
CREATE TABLE IF NOT EXISTS ml_predictions (
  symbol TEXT, prediction_date TEXT, ml_score_6m REAL, ml_score_12m REAL,
  final_ml_score REAL, ml_rank REAL, model_version TEXT,
  PRIMARY KEY (symbol, prediction_date)
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn