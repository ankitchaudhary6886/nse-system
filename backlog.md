# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.

---

## A. RULES  (always active)

- **R1**–**R27** as previously logged.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
I1–I7 as logged.

### Session 2 — 2026-09-12 (midday → evening)
I8–I34 as logged.

### Session 2 (continued) — 2026-09-12 (evening)
- **I35** Proceed with ID44 (fundamentals fix). Step 1: probe TV.
- **I36** Step 2: rewrite fetcher, quality-only Multibagger.
- **I37** Fix score outlier bug — percentile scoring.
- **I38** Proceed with Phase 3 + Phase 4. Start Phase 3 with ID47
          (candle behaviour analytics).

---

## C. DEMANDS
D1–D6 as previously logged.

---

## D. IDEAS

### ID1–ID45 as previously logged.

### ID46 — Signature matching · **PLANNED (Phase 3, next)**
Find the N closest historical setups across ALL symbols to today's
live setup. Show pooled stats. Requires a global historical-setup table
built once (background job).

### ID47 — Candle behaviour analytics · **DONE this batch**
Mother bar of every historical setup is classified (inside / hammer /
inverse hammer / doji / wide / normal), grouped, and hit rates computed
per category. Current setup is matched against its category.

### ID48 — Pattern condition transparency · **PLANNED (Phase 3)**
Show per-condition pass/fail on every pattern tag. Currently patterns
only report aggregate score.

### ID49 — Time-machine chart markers · **PLANNED (Phase 3)**
Historical pattern signals overlaid on the chart, coloured by outcome.
Click a marker → that historical setup's details.

### ID50 — Compare mode · **PLANNED (Phase 3)**
Multi-select 2-4 stocks → side-by-side metrics table.

### ID51 — Unified stock card · **PLANNED (Phase 3)**
One card component used everywhere. Currently three card builders exist.

### ID52 — Data source plugins · **PLANNED (Phase 4)**
Standard interface for TradingView / Yahoo / NSE / Chartink / ScanX /
screener.in. Auto-discovery, fallback chain, health dashboard.

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + **FCA** (candle behaviour analytics).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R27 | Rules                    | Active       |
| I1–I38 | Instructions             | Applied      |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Score normalization       | DONE         |
| ID47  | Candle behaviour          | DONE         |
| ID46  | Signature matching        | NEXT (P3)    |
| ID48  | Pattern transparency      | PLANNED P3   |
| ID49  | Time-machine markers      | PLANNED P3   |
| ID50  | Compare mode              | PLANNED P3   |
| ID51  | Unified stock card        | PLANNED P3   |
| ID52  | Data source plugins       | PLANNED P4   |

---

## H. REMAINING / LEFT

### Phase 3 (this session)
- ID46 Signature matching — NEXT
- ID48 Pattern transparency
- ID49 Time-machine chart markers
- ID50 Compare mode
- ID51 Unified stock card

### Phase 4
- ID52 Data source plugin system
- Growth data source integration

### Deferred
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync (missing GCP key)