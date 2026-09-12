# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.
- Survives chat migration.

---

## A. RULES  (always active)

- **R1**–**R26** as previously logged.
- **R27** **Data source fixes are probed, not guessed.** Before rewriting
          a fetcher, first probe what the source actually returns.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
- **I1**–**I7** as previously logged.

### Session 2 — 2026-09-12 (midday → evening)
- **I8**–**I34** as previously logged.

### Session 2 (continued) — 2026-09-12 (evening)
- **I35** Proceed with ID44 (fundamentals fix). Step 1: probe TV.
- **I36** Step 2: rewrite `fundamentals_tv.py` with only the working
          columns; add derived fields; extend `fundamentals` schema with
          6 new columns; adjust Multibagger seed to quality-only.

---

## C. DEMANDS
D1–D6 as previously logged.

---

## D. IDEAS

### ID1–ID43 as previously logged.
### ID44 — Fundamentals data fix · **DONE this batch**
TV India returns no growth data, no shareholding data, no price_to_book.
Probe confirmed 48 working columns. Rewrote fetcher to use only those.
Multibagger seed now quality-only (ROCE, ROE, D/E, CFO+, op margin).
Growth filters must come from another source (Phase 4).
### ID45 — Signature matching · **PLANNED (Phase 3)**
### ID46 — Candle feature statistics · **PLANNED (Phase 3)**

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list, plus **FTR** (TV column probe), **FDF** (fundamentals v5).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R27 | Rules                    | Active       |
| I1–I36 | Instructions             | Applied      |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Signature matching        | PLANNED P3   |
| ID46  | Candle feature stats      | PLANNED P3   |

---

## H. REMAINING / LEFT

### Immediate NEXT
- **Growth data** for Multibagger — need a second source
  (screener.in, Chartink, Yahoo fundamentals) — Phase 4 (ID32).

### Phase 3
- ID45 Signature matching
- ID46 Candle behaviour analytics
- ID30 Pattern transparency
- ID31 Time-machine chart markers
- ID36 Compare mode
- ID33 Finish unified stock card rollout

### Phase 4
- ID32 Data source plugin system
- Growth / shareholding data source

### Deferred
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py (nse.service)
- Google Sheets sync (missing GCP key)

---

## I. HOW THIS FILE GROWS
As previously documented.