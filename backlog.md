# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.

---

## A. RULES  (always active)

- **R1**–**R23** unchanged (see previous entries). Summary:
  whole files · plain English · VS Code + Oracle VM · laptop push / VM pull ·
  batched blocks · skip ops unless asked · auto-backlog new ideas ·
  log every execution · no pausing · 3-4 edits/response ·
  execute after machine complete · fast feedback loops (~5s) ·
  PF-driven verdicts · sweep parameters · prefer simpler on ties ·
  multi-window WF · system identifies, owner decides ·
  log every instruction immediately · full picture per candidate ·
  central config · graceful skips for optional integrations.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I23 (see EXECUTION_LOG)
I24 ID22b shipped — research universe view.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID21 · DONE / partial (see EXECUTION_LOG)

### ID22 — Research Cockpit v1 · **DONE**
Per-symbol 5y analysis. Cached 7 days. CLI + API + UI.

### ID22b — Research Universe · **DONE this batch**
Today's setups (SWING + ALL_WEATHER + top TREND) joined with cached
per-symbol stats. Cached per symbol, refreshed on demand.
Endpoint: `/api/research-universe`
Cache table: `research_cache(symbol, computed_at, payload)`.
UI panel: "Research Universe" in Overview tab.
Shows: n setups, n triggered, P(+1R / +2R / +3R), median MFE/MAE.
Owner scans the table, picks what interests them.

### ID22c — Auto-warm cache nightly · **NEXT**
Scheduler job after swing scan: for each symbol with a signal today,
compute research stats and cache them. Then universe view is always
instant. Currently cold-cache items show "miss".

### ID23 — Sector-level research · **FUTURE**
Aggregate cockpit by sector: "Energy setups have P(+2R)=0.42 historically".
Context layer for cross-sector comparison.

### ID24 — Candle behaviour analytics · **FUTURE**
Extend cockpit: for each historical setup, classify the mother bar
(inside, hammer-like, tight-cluster width vs ATR) and see hit rate
conditioned on that feature.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system · IM4 Research cockpit.

---

## F. FEATURES COMPLETED
(all prior) + Research Cockpit v1 (ID22) + Research Universe (ID22b)

---

## G. STATUS SUMMARY (rows added)
| ID22b | Research universe      | DONE this batch |
| ID22c | Warm cache nightly     | NEXT            |
| ID23 | Sector-level research   | FUTURE          |
| ID24 | Candle analytics        | FUTURE          |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync