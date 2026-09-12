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
I35–I37 as logged.

### Session 2 (Phase 3 begins)
- **I38** Proceed with Phase 3 + Phase 4. Start Phase 3 with ID47.
- **I39** ID47 verified. Proceed with ID46 (signature matching).

---

## C. DEMANDS
D1–D6 as previously logged.

---

## D. IDEAS

### ID1–ID45 as previously logged.
### ID46 — Signature matching · **DONE this batch**
Global `setup_pool` table built by `build_setup_pool.py`. For any live
setup, find 30 nearest historical setups by L1 distance on z-scored
features. Show pooled hit rates, MFE/MAE, outcome mix, sector breakdown.
### ID47 — Candle behaviour analytics · **DONE** (previous batch)
### ID48 — Pattern condition transparency · **NEXT (Phase 3)**
### ID49 — Time-machine chart markers · **PLANNED (Phase 3)**
### ID50 — Compare mode · **PLANNED (Phase 3)**
### ID51 — Unified stock card · **PLANNED (Phase 3)**
### ID52 — Data source plugins · **PLANNED (Phase 4)**

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + **FSM** (signature matching).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R27 | Rules                    | Active       |
| I1–I39 | Instructions             | Applied      |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Score normalization       | DONE         |
| ID46  | Signature matching        | DONE         |
| ID47  | Candle behaviour          | DONE         |
| ID48  | Pattern transparency      | NEXT         |
| ID49  | Time-machine markers      | PLANNED P3   |
| ID50  | Compare mode              | PLANNED P3   |
| ID51  | Unified stock card        | PLANNED P3   |
| ID52  | Data source plugins       | PLANNED P4   |

---

## H. REMAINING / LEFT

### Phase 3 (this session)
- ID48 Pattern transparency — NEXT
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