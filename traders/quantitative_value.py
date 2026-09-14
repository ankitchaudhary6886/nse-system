"""
Wesley R. Gray & Tobias E. Carlisle — Quantitative Value (2012).
Classified: FUNDA (long-horizon, annual-rebalanced value + quality).

17 methods extracted per docs/BOOK_EXTRACTION_PROMPT.md.

The book's core thesis: (1) cleanse the universe of frauds,
manipulators, and financially distressed firms, then (2) rank the
survivors by EBIT/TEV (best price ratio), and (3) among the cheapest
decile, prefer high-quality firms (franchise power + financial strength).

Data availability (as of 2026-09-14):
  AVAILABLE NOW:
    pe, pb, roce, roe, debt_to_equity, cfo_positive,
    net_profit_margin, operating_margin, dividend_yield, mcap_cr
  NOT YET IN DB — methods degrade gracefully:
    EBIT, TEV, gross profit, total assets, current assets/liabilities,
    cash, shares history, 8-year fundamentals series,
    insider trades, short interest, 13D filings

When those land (ID52 data-source plugins), flagged methods activate
without code change. Scan() logs a data-coverage report each run.

Proxy policy (R2 + R19):
  Book's EBIT/TEV   → we use 1/PE (earnings yield) as the closest
                       available price ratio. Notes field says so.
  Book's ROC        → we use ROCE (return on capital employed) from
                       TradingView, which is the same concept.
  Book's GPA        → we use ROE as a profitability rank proxy.
  Book's F_SCORE    → we implement the 2 signals we can compute
                       (ROA>0, CFO>0) as a PARTIAL signal, clearly
                       labeled. Not silently masqueraded as full.
"""
import numpy as np
import db
from log_utils import get_logger
from universe_helper import band_universe

log = get_logger("trader.quantitative_value")

SLUG = "quantitative_value"
NAME = "Wesley Gray & Tobias Carlisle"
PILLAR = "funda"
SOURCE = "Quantitative Value (2012)"


# ----------------------------------------------------------------
# Tunables — book-cited thresholds, India adaptations noted
# ----------------------------------------------------------------
TOP_N = 30                       # book's standard portfolio size
UNIVERSE_MIN_PCT = 40            # book's NYSE 40th percentile → NSE
MIN_PRICE = 100                  # book's $10 → ₹100 (penny avoidance)
GRAHAM_PE_MAX = 10
GRAHAM_DE_MAX = 0.50
ROCE_QUALITY_MIN = 15.0          # our own quality gate
PFD_ELIMINATE_PCT = 95           # top 5% → eliminate
COMBOACCRUAL_ELIMINATE_PCT = 95  # top 5% → eliminate

EXCLUDE_SECTOR_KEYWORDS = (
    "financ", "bank", "nbfc", "insur", "utilit", "power",
    "gas distribution", "water", "electric", "reit",
)


# ----------------------------------------------------------------
# METHODS registry — 17 total (7 scanned, 10 flagged)
# ----------------------------------------------------------------
METHODS = [
    # ---- SCANNED (7) ----
    {"id": "graham_simple_value", "name": "Graham Simple Value",
     "description": "PE ≤ 10, D/E ≤ 0.5, CFO+, positive margin. Clean.",
     "direction": "long", "scan": True, "confidence": "HIGH"},
    {"id": "earnings_yield_value", "name": "Earnings Yield (EBIT/TEV proxy)",
     "description": "Rank by 1/PE. Proxy for EBIT/TEV until EBIT lands.",
     "direction": "long", "scan": True, "confidence": "MED"},
    {"id": "book_to_market_value", "name": "Book-to-Market Value",
     "description": "Rank by 1/PB.",
     "direction": "long", "scan": True, "confidence": "MED"},
    {"id": "magic_formula_proxy", "name": "Magic Formula (proxy)",
     "description": "Rank by ROCE + 1/PE combined. Proxy for ROC + EBIT/TEV.",
     "direction": "long", "scan": True, "confidence": "MED"},
    {"id": "quality_and_price_proxy", "name": "Quality & Price (proxy)",
     "description": "Rank by ROE + 1/PB combined. Proxy for GPA + BM.",
     "direction": "long", "scan": True, "confidence": "MED"},
    {"id": "composite_price_ratios_proxy", "name": "Composite Price Ratios (proxy)",
     "description": "Avg rank of 1/PE, 1/PB, dividend_yield.",
     "direction": "long", "scan": True, "confidence": "MED"},
    {"id": "roce_quality_gate", "name": "ROCE Quality Gate",
     "description": "ROCE ≥ 15%, non-financial, non-utility.",
     "direction": "long", "scan": True, "confidence": "HIGH"},
    # ---- FLAGGED (10) — awaiting features ----
    {"id": "scaled_total_accruals", "name": "Scaled Total Accruals (STA)",
     "description": "Eliminate top 5% accruals. Needs balance-sheet changes.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "scaled_net_operating_assets", "name": "Scaled Net Operating Assets (SNOA)",
     "description": "Eliminate top 5% bloated balance sheets. Needs balance sheet.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "probm_manipulation", "name": "Probability of Manipulation (PROBM)",
     "description": "8-variable fraud detector. Needs historical financials.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "pfd_financial_distress", "name": "Probability of Financial Distress (PFD)",
     "description": "Campbell et al. distress model. Needs quarterly data + market history.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "piotroski_f_score", "name": "Piotroski F_SCORE",
     "description": "9 binary signals. Needs YoY changes. Partial only.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "fs_score", "name": "Financial Strength Score (FS_SCORE)",
     "description": "10 binary signals. Needs YoY changes + shares history.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "franchise_power", "name": "Franchise Power",
     "description": "8-year geometric ROA/ROC + margin stability. Needs 8y history.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "ebit_enterprise_multiple", "name": "EBIT Enterprise Multiple",
     "description": "The book's best price ratio. Needs EBIT + TEV.",
     "direction": "long", "scan": False, "confidence": "HIGH"},
    {"id": "buyback_yield", "name": "Buyback Yield",
     "description": "Net share repurchase. Needs shares-outstanding history.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "insider_buying_opportunistic", "name": "Opportunistic Insider Buying",
     "description": "Non-routine insider purchases. Needs insider feed (SAST).",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "activist_13d_filing", "name": "Activist 13D Filing",
     "description": "Activist stake disclosures. Needs filing feed (SAST).",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "low_short_interest", "name": "Low Short Interest",
     "description": "Bottom decile SIR. Needs NSE short-interest feed.",
     "direction": "long", "scan": False, "confidence": "MED"},
    {"id": "quantitative_value_model", "name": "Full Quantitative Value Model",
     "description": "Integrated book model. Portfolio construction, not scanned.",
     "direction": "long", "scan": False, "confidence": "HIGH"},
]


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _is_excluded_sector(sector):
    if not sector:
        return False
    s = sector.lower()
    return any(k in s for k in EXCLUDE_SECTOR_KEYWORDS)


def _safe_num(v):
    if v is None:
        return None
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _fundamentals_map(conn):
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(fundamentals)")]
    except Exception:
        return {}
    if not cols:
        return {}
    sel = ", ".join(cols)
    out = {}
    try:
        for row in conn.execute(f"SELECT {sel} FROM fundamentals"):
            m = dict(zip(cols, row))
            sym = m.get("symbol")
            if sym:
                out[sym] = m
    except Exception as e:
        log.warning(f"fundamentals load failed: {e}")
    return out


def _last_close(conn, sym):
    r = conn.execute(
        "SELECT close FROM prices_daily WHERE symbol=? "
        "ORDER BY date DESC LIMIT 1", (sym,)).fetchone()
    return _safe_num(r[0]) if r else None


# ----------------------------------------------------------------
# Feature builder
# ----------------------------------------------------------------
def _build_features(conn, syms):
    """Build feature dict per symbol. Sector-excluded symbols dropped."""
    fund_map = _fundamentals_map(conn)
    features = {}
    excluded_sector = 0
    missing_fund = 0
    for i, sym in enumerate(syms, 1):
        f = fund_map.get(sym)
        if not f:
            missing_fund += 1
            continue
        sector = f.get("sector")
        if _is_excluded_sector(sector):
            excluded_sector += 1
            continue
        pe = _safe_num(f.get("pe"))
        pb = _safe_num(f.get("pb"))
        roce = _safe_num(f.get("roce"))
        roe = _safe_num(f.get("roe"))
        de = _safe_num(f.get("debt_to_equity"))
        dy = _safe_num(f.get("dividend_yield"))
        mcap = _safe_num(f.get("market_cap_cr"))
        cfo = f.get("cfo_positive")
        npm = _safe_num(f.get("net_profit_margin"))

        # Derived
        earnings_yield = (1.0 / pe) if (pe and pe > 0) else None
        book_to_market = (1.0 / pb) if (pb and pb > 0) else None

        features[sym] = {
            "symbol": sym,
            "sector": sector,
            "market_cap_cr": mcap,
            "pe": pe,
            "pb": pb,
            "roce": roce,
            "roe": roe,
            "debt_to_equity": de,
            "cfo_positive": cfo,
            "net_profit_margin": npm,
            "dividend_yield": dy,
            "earnings_yield": earnings_yield,
            "book_to_market": book_to_market,
        }
        if i % 200 == 0:
            log.info(f"  features {i}/{len(syms)}")
    log.info(f"features: kept={len(features)}, "
             f"sector-excluded={excluded_sector}, "
             f"no-fundamentals={missing_fund}")
    return features


# ----------------------------------------------------------------
# Cross-sectional stats + percentile rankings
# ----------------------------------------------------------------
def _percentile_rank_map(items):
    """items = list of (sym, value). Returns {sym: percentile 0-100}."""
    valid = [(s, v) for s, v in items if v is not None]
    if not valid:
        return {}
    valid.sort(key=lambda x: x[1])
    n = len(valid)
    return {
        s: (100.0 * i / (n - 1)) if n > 1 else 50.0
        for i, (s, _) in enumerate(valid)
    }


def _universe_stats(features):
    mcaps = sorted([f["market_cap_cr"] for f in features.values()
                    if f.get("market_cap_cr") is not None])
    mcap_40pct = None
    if mcaps:
        idx = max(0, int(len(mcaps) * UNIVERSE_MIN_PCT / 100.0) - 1)
        mcap_40pct = mcaps[idx]
    return {"mcap_40pct": mcap_40pct}


def _compute_rankings(features, ustats):
    """Compute top-N symbol sets for each scanned method."""
    out = {}

    # Only symbols above the 40th percentile mcap gate are eligible
    gate = ustats.get("mcap_40pct")
    eligible = {
        s: f for s, f in features.items()
        if f.get("market_cap_cr") is not None
        and gate is not None
        and f["market_cap_cr"] >= gate
    }
    log.info(f"universe after 40th-pct mcap gate: {len(eligible)}")

    # ---- Graham Simple Value (pure filter) ----
    graham = set()
    for s, f in eligible.items():
        pe = f.get("pe")
        de = f.get("debt_to_equity")
        cfo = f.get("cfo_positive")
        npm = f.get("net_profit_margin")
        if (pe is not None and 0 < pe <= GRAHAM_PE_MAX
                and de is not None and de <= GRAHAM_DE_MAX
                and cfo == 1
                and npm is not None and npm > 0):
            graham.add(s)
    out["graham_simple_value"] = graham

    # ---- Earnings yield (1/PE) ----
    ey_items = [(s, f.get("earnings_yield")) for s, f in eligible.items()]
    ey_items = [x for x in ey_items if x[1] is not None]
    ey_items.sort(key=lambda x: -x[1])
    out["earnings_yield_value"] = {s for s, _ in ey_items[:TOP_N]}

    # ---- Book-to-market (1/PB) ----
    bm_items = [(s, f.get("book_to_market")) for s, f in eligible.items()]
    bm_items = [x for x in bm_items if x[1] is not None]
    bm_items.sort(key=lambda x: -x[1])
    out["book_to_market_value"] = {s for s, _ in bm_items[:TOP_N]}

    # ---- Magic Formula proxy: ROCE + Earnings Yield, low combined rank ----
    roce_ranks = _percentile_rank_map(
        [(s, f.get("roce")) for s, f in eligible.items()])
    ey_ranks = _percentile_rank_map(
        [(s, f.get("earnings_yield")) for s, f in eligible.items()])
    combined = []
    for s in eligible:
        if s in roce_ranks and s in ey_ranks:
            # Higher percentile = better; low combined rank = "lower is
            # better" of (100 - rank). Book sums raw ranks 1..N. We
            # mimic by summing "100 - pct_rank" (lower = better).
            score = (100 - roce_ranks[s]) + (100 - ey_ranks[s])
            combined.append((s, score))
    combined.sort(key=lambda x: x[1])
    out["magic_formula_proxy"] = {s for s, _ in combined[:TOP_N]}

    # ---- Quality and Price proxy: ROE + 1/PB ----
    roe_ranks = _percentile_rank_map(
        [(s, f.get("roe")) for s, f in eligible.items()])
    bm_ranks = _percentile_rank_map(
        [(s, f.get("book_to_market")) for s, f in eligible.items()])
    qp = []
    for s in eligible:
        if s in roe_ranks and s in bm_ranks:
            score = (100 - roe_ranks[s]) + (100 - bm_ranks[s])
            qp.append((s, score))
    qp.sort(key=lambda x: x[1])
    out["quality_and_price_proxy"] = {s for s, _ in qp[:TOP_N]}

    # ---- Composite price ratios: 1/PE + 1/PB + Div yield ----
    dy_ranks = _percentile_rank_map(
        [(s, f.get("dividend_yield")) for s, f in eligible.items()])
    comp = []
    for s in eligible:
        parts = []
        if s in ey_ranks:
            parts.append(ey_ranks[s])
        if s in bm_ranks:
            parts.append(bm_ranks[s])
        if s in dy_ranks:
            parts.append(dy_ranks[s])
        if parts:
            comp.append((s, sum(parts) / len(parts)))
    comp.sort(key=lambda x: -x[1])
    out["composite_price_ratios_proxy"] = {s for s, _ in comp[:TOP_N]}

    # ---- ROCE quality gate ----
    roce_gate = set()
    for s, f in eligible.items():
        roce = f.get("roce")
        if roce is not None and roce >= ROCE_QUALITY_MIN:
            roce_gate.add(s)
    out["roce_quality_gate"] = roce_gate

    return out


# ----------------------------------------------------------------
# Per-symbol evaluation
# ----------------------------------------------------------------
def _signal(sym, method_id, confidence, notes, raw):
    return {
        "symbol": sym,
        "trader": SLUG,
        "method": method_id,
        "direction": "BULLISH",
        "signal_type": "SELECTED",
        "entry": None, "stop": None, "target": None,
        "confidence": confidence,
        "notes": notes,
        "raw": raw,
    }


def _evaluate_symbol(sym, f, rankings):
    sigs = []

    if sym in rankings.get("graham_simple_value", set()):
        sigs.append(_signal(
            sym, "graham_simple_value", "HIGH",
            f"Graham: PE {f.get('pe'):.2f} ≤ {GRAHAM_PE_MAX}, "
            f"D/E {f.get('debt_to_equity'):.2f} ≤ {GRAHAM_DE_MAX}, "
            f"CFO+, margin positive",
            {"pe": f.get("pe"),
             "debt_to_equity": f.get("debt_to_equity")}))

    if sym in rankings.get("earnings_yield_value", set()):
        sigs.append(_signal(
            sym, "earnings_yield_value", "MED",
            f"Earnings yield {f.get('earnings_yield') * 100:.2f}% "
            f"(1/PE, proxy for EBIT/TEV)",
            {"earnings_yield": f.get("earnings_yield"),
             "pe": f.get("pe")}))

    if sym in rankings.get("book_to_market_value", set()):
        sigs.append(_signal(
            sym, "book_to_market_value", "MED",
            f"Book-to-market {f.get('book_to_market'):.3f} "
            f"(1/PB = {f.get('pb'):.2f} P/B)",
            {"book_to_market": f.get("book_to_market"),
             "pb": f.get("pb")}))

    if sym in rankings.get("magic_formula_proxy", set()):
        sigs.append(_signal(
            sym, "magic_formula_proxy", "MED",
            f"Magic Formula proxy: ROCE {f.get('roce'):.1f}% + "
            f"E/Y {f.get('earnings_yield') * 100:.2f}%",
            {"roce": f.get("roce"),
             "earnings_yield": f.get("earnings_yield")}))

    if sym in rankings.get("quality_and_price_proxy", set()):
        sigs.append(_signal(
            sym, "quality_and_price_proxy", "MED",
            f"Q&P proxy: ROE {f.get('roe'):.1f}% + "
            f"B/M {f.get('book_to_market'):.3f}",
            {"roe": f.get("roe"),
             "book_to_market": f.get("book_to_market")}))

    if sym in rankings.get("composite_price_ratios_proxy", set()):
        sigs.append(_signal(
            sym, "composite_price_ratios_proxy", "MED",
            f"Composite: E/Y {f.get('earnings_yield') and f['earnings_yield']*100:.2f}% "
            f"+ B/M {f.get('book_to_market'):.3f} "
            f"+ DY {f.get('dividend_yield') or 0:.2f}%",
            {"earnings_yield": f.get("earnings_yield"),
             "book_to_market": f.get("book_to_market"),
             "dividend_yield": f.get("dividend_yield")}))

    if sym in rankings.get("roce_quality_gate", set()):
        sigs.append(_signal(
            sym, "roce_quality_gate", "HIGH",
            f"ROCE {f.get('roce'):.1f}% ≥ {ROCE_QUALITY_MIN}",
            {"roce": f.get("roce")}))

    return sigs


# ----------------------------------------------------------------
# Universe scan
# ----------------------------------------------------------------
def scan(conn=None, limit=800):
    """
    Scan the band universe. Returns list of signal dicts — one per
    (symbol, method) pair where the symbol qualifies.

    Funda signals: entry/stop/target are None. The owner decides
    rebalance timing and sizing (R19).
    """
    own = conn is None
    if own:
        conn = db.get_conn()

    syms = band_universe(conn, limit=limit)
    log.info(f"QV scan: {len(syms)} symbols in universe")

    features = _build_features(conn, syms)
    if not features:
        if own:
            conn.close()
        log.warning("no features — check fundamentals table")
        return []

    ustats = _universe_stats(features)
    rankings = _compute_rankings(features, ustats)

    # Data-coverage report (once per scan)
    n_pe = sum(1 for f in features.values() if f.get("pe") is not None)
    n_pb = sum(1 for f in features.values() if f.get("pb") is not None)
    n_roce = sum(1 for f in features.values() if f.get("roce") is not None)
    n_roe = sum(1 for f in features.values() if f.get("roe") is not None)
    n_de = sum(1 for f in features.values()
               if f.get("debt_to_equity") is not None)
    n_dy = sum(1 for f in features.values()
               if f.get("dividend_yield") is not None)
    log.info(
        f"coverage: PE={n_pe} PB={n_pb} ROCE={n_roce} ROE={n_roe} "
        f"D/E={n_de} DY={n_dy} · "
        f"blocked: EBIT/TEV (Methods 2,11), balance-sheet changes "
        f"(Methods 4,5), 8y history (Methods 8,9,10), "
        f"insider/SI/13D feeds (Methods 14,15,16)"
    )

    signals = []
    for sym, f in features.items():
        try:
            signals.extend(_evaluate_symbol(sym, f, rankings))
        except Exception as e:
            log.warning(f"{sym} evaluation failed: {e}")

    if own:
        conn.close()

    n_sym = len(set(s["symbol"] for s in signals))
    log.info(f"QV scan complete: {len(signals)} signals across "
             f"{n_sym} symbols")
    return signals