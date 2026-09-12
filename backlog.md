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
- **I1**–**I7** as previously logged.

### Session 2 — 2026-09-12 (midday → evening)
- **I8**–**I34** as previously logged.

### Session 2 (continued) — 2026-09-12 (evening)
- **I35** Proceed with ID44 (fundamentals fix). Step 1: probe TV.
- **I36** Step 2: rewrite fetcher, add derived fields, quality-only
          Multibagger.
- **I37** Fix score outlier bug — percentile scoring.

---

## C. DEMANDS
D1–D6 as previously logged.

---

## D. IDEAS

### ID1–ID43 as previously logged.
### ID44 — Fundamentals data fix · **DONE** (863 rows, all core fields)
### ID45 — Score normalization · **DONE this batch**
Percentile ranks replace raw-value scores. Outliers no longer dominate.
### ID46 — Signature matching · **PLANNED (Phase 3)**
### ID47 — Candle feature statistics · **PLANNED (Phase 3)**

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + **FDF** (fundamentals v5) + **FPS** (percentile scoring).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R27 | Rules                    | Active       |
| I1–I37 | Instructions             | Applied      |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Score normalization       | DONE         |
| ID46  | Signature matching        | PLANNED P3   |
| ID47  | Candle feature stats      | PLANNED P3   |

---

## H. REMAINING / LEFT

### Immediate NEXT
- Growth data source for Multibagger (Phase 4 / ID32).

### Phase 3
- ID46 Signature matching
- ID47 Candle behaviour analytics
- ID30 Pattern transparency
- ID31 Time-machine chart markers
- ID36 Compare mode
- ID33 Finish unified stock card rollout

### Phase 4
- ID32 Data source plugin system

### Deferred
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync (missing GCP key)