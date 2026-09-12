# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.

---

## A. RULES (unchanged, summary)
R1–R23 as recorded. Highlights: whole files · plain English ·
laptop push / VM pull · batch per machine · skip ops unless asked ·
auto-backlog new ideas · log every execution · no pausing ·
3-4 edits/response · fast feedback loops · PF-driven verdicts ·
sweep parameters · multi-window WF · system identifies, owner decides ·
log every instruction immediately · full picture per candidate ·
central config · graceful skips for optional integrations.

### New
- **R24** Research tables are sortable + colour-coded by sample size.
          Reliability is visible at a glance: green ≥10, amber 5-9,
          grey <5, dash for none.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I24 (see EXECUTION_LOG)

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID22c · DONE / partial (see EXECUTION_LOG)

### ID23 — Sector-level aggregation · **DONE this batch**
`research_cockpit.sector_aggregate()` pools raw setups from every
cached symbol in a sector, then recomputes stats on the pool.
Endpoint: `/api/research-sector`
UI panel: "Research Sectors" in Overview tab.
Sortable + reliability-coloured.

### ID23b — Reliability colour coding · **DONE this batch**
`rel-pill` classes: `rel-strong` (≥10), `rel-mod` (5-9),
`rel-thin` (1-4), `rel-none` (0).
Applied to n column in both universe and sector tables.

### ID23c — Sortable columns · **DONE this batch**
Click any table header to sort ascending/descending.
Sort state preserved across re-renders.

### ID24 — Candle behaviour analytics · **FUTURE**
Classify each historical setup's mother bar (inside, hammer, tight
cluster width vs ATR) and compute hit rate conditioned on that feature.
Adds a context layer to the cockpit.

### ID25 — Sector strength overlay · **FUTURE**
Join sector aggregation with sector_rs from sector_gate. See if
hit rates differ across sector regimes.

### ID26 — Setup similarity matching · **FUTURE**
For a live setup, find the N closest historical setups (across all
symbols) by feature distance (impulse %, PB depth, shape score, etc.)
and show only those stats. Personalised context, not symbol-only.

---

## E. IMAGINATIONS (unchanged)
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system · IM4 Research cockpit.

---

## F. FEATURES COMPLETED
### FRC Research Cockpit v1 · DONE
### FRU Research Universe · DONE
### FRS Sector Aggregation · DONE
### FSRT Sortable + Reliability UI · DONE

---

## G. STATUS SUMMARY (added rows)
| ID23  | Sector aggregation      | DONE this batch |
| ID23b | Reliability colours     | DONE this batch |
| ID23c | Sortable tables         | DONE this batch |
| ID24  | Candle behaviour        | FUTURE          |
| ID25  | Sector strength overlay | FUTURE          |
| ID26  | Setup similarity        | FUTURE          |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync