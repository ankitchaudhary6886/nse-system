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
I1–I7.

### Session 2 — 2026-09-12 (midday → evening)
I8–I34.

### Session 2 (continued) — 2026-09-12 (evening)
I35–I40 as logged.

### Session 3 — 2026-09-13
- **I41** Add weekly setup_pool rebuild job (Sunday 06:00 IST, 800
          symbols, step=5). Shipped.
- **I42** Proceed with ID48 + ID49 (pattern transparency + chart
          markers).

---

## C. DEMANDS
D1–D6 as previously logged.

---

## D. IDEAS

### ID1–ID47 as previously logged.
### ID48 — Pattern condition transparency · **DONE this batch**
Every pattern detector now records a `checks` list of conditions
(name + got + ok). Stored in `pattern_tags.params` JSON. UI shows
expandable "Show conditions (N)" toggle on each pattern card.
### ID49 — Time-machine chart markers · **DONE this batch**
New endpoint `/api/patterns/history/{symbol}`. Research cockpit chart
now overlays markers at every historical pattern signal — green up
arrow (WIN), red down arrow (LOSS), yellow circle (TIMEOUT/EXPIRED),
blue square (OPEN/undefined). Bearish patterns get downward arrow.
### ID50 — Compare mode · **NEXT (Phase 3)**
### ID51 — Unified stock card · **PLANNED (Phase 3)**
### ID52 — Data source plugins · **PLANNED (Phase 4)**

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + **FPT** (pattern transparency) + **FTM** (time-machine
chart markers).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R27 | Rules                    | Active       |
| I1–I42 | Instructions             | Applied      |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Score normalization       | DONE         |
| ID46  | Signature matching        | DONE         |
| ID47  | Candle behaviour          | DONE         |
| ID48  | Pattern transparency      | DONE         |
| ID49  | Time-machine markers      | DONE         |
| ID50  | Compare mode              | NEXT         |
| ID51  | Unified stock card        | PLANNED P3   |
| ID52  | Data source plugins       | PLANNED P4   |

---

## H. REMAINING / LEFT

### Phase 3
- ID50 Compare mode — NEXT
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