# Chart re-verify report — clean MA set + synced RSI-14 30/70 pane

Owner doubt being answered: *"it should show 10,20,50 ema/sma (whatevers important), and price crossing RSI 30-70 band in bottom like angel one"*.

- Files written: `terminal/static/app.js`, `terminal/static/fintech.css` (CSS appended only).
- `terminal/static/index.html` was **not** touched in this pass (it already contains `#chartPrice` + `#chartRsi` + `#chartReadout` inside `#chart`). `tools/**` was run, never edited.
- Verification server: `127.0.0.1:8021` (`/api/health` → 200), killed at the end of the pass.
- Run order: eval → shots → audit → `test_*.py`. The marker-text tweak in §6 was made last, so the final eval and audit were re-run on the frozen file (`eval-final-1440.json`, `eval-final-390.json`).

---

## 1. `cockpit_chart` payload contract actually observed

Handler: `terminal_api.py` → `@app.get("/api/cockpit/{symbol}/chart")`, `def cockpit_chart(...)` (≈ line 950).
Live probe on 8021 (`GET /api/cockpit/KEI/chart`, 2026-10-07): HTTP 200, 97,493 bytes.

```
keys = symbol, candles, ema10, ema20, ema50, ema200, swing
candles      420 items  {"time":"YYYY-MM-DD","open":f,"high":f,"low":f,"close":f}
ema10/20/50/200  420 items each  {"time":"YYYY-MM-DD","value":f}
swing        null for KEI (present as a key; non-null only when SetupDetector fires)
first bar 2024-12-17 4381.98 | last bar 2026-08-21 close 5527.60
candle0 = {"time":"2024-12-17","open":4440.06,"high":4467.00,"low":4350.75,"close":4381.98}
ema200_0 = {"time":"2024-12-17","value":4381.98}   (ewm from bar 0, so no leading nulls)
```

**No SMA key exists in the payload** (`payloadHasSmaKey: false`), no RSI key, no volume, no intraday. The handler tails the last 420 rows (`df = ...tail(420)`) and derives the four EMAs with `ewm(span=N, adjust=False)`.

Consequence: SMA 10/20 and RSI-14 are computed client-side. No backend edit was needed or made.

## 2. Final DEFAULT MA set, and why the others are off

**Drawn on load: `SMA 10`, `EMA 20`, `EMA 50`, `EMA 200` — 4 lines (the cap).**
**Available but OFF: `EMA 10`, `SMA 20`.**

| Series | Default | Style | Why |
|---|---|---|---|
| SMA 10 | ON | cyan `#22d3ee`, dashed | The owner's "10". There was **no simple moving average anywhere in the codebase** before this pass. Immediate trend of the close. |
| EMA 20 | ON | amber `#fbbf24`, solid | The system's short-term trend / pullback-zone reference: `terminal_api.py` exposes SetupDetector's `ema_proximity` as `swing.zone`, and the model features include `d10`/`d20` ("distance from the short/medium-term average price", `FEATURE_PLAIN` in app.js). |
| EMA 50 | ON | violet `#a78bfa`, solid | Medium-term trend; used by the terminal's own scan surfaces (`scanners.js` prints `EMA50 ₹… · EMA200 ₹…`; features `slope50`, `days_above_50_30`). |
| EMA 200 | ON | slate `#94a3b8`, solid | Long-term regime filter used by every scan/feature (`slope200`, `above200`, `days_above_200_30`, `ema200_dist_z`; `scanners.js`, `research.js` `["ema20","ema50","ema200"]`). Removing it hides the regime line the rest of the terminal reasons about. |
| EMA 10 | OFF | blue `#60a5fa`, solid | Duplicates SMA 10's information at almost the same level; two 10-period lines is ink without information. |
| SMA 20 | OFF | pink `#f472b6`, dashed | Sits directly on top of EMA 20 on this data. |

Reasoning: the terminal's own evidence is 20/50/200, and the owner asked for a 10/20/50 read — SMA 10 + EMA 20 + EMA 50 satisfies "10,20,50" while EMA 200 keeps the regime line. Four lines is the readable ceiling; everything else is one click away.

Every average has an honest toggle: the toolbar shows `Averages (4 on)`, which opens a chip row (one chip per average the loaded symbol has) where each chip prints `on`/`off` and its colour, and `aria-pressed` matches the series. State persists for the session in `sessionStorage["nse.showMA"]` (a choice written by the previous `nse.showEma10` toggle is migrated). Style convention: **SMA dashed, EMA solid** — the same convention is used in the legend swatches.

## 3. RSI 30/70 pane: what is actually true

- **No pane API in the served library.** `lightweight-charts@4.1.3` standalone: `typeof chart.addPane === "function"` → `false`, `typeof chart.panes === "function"` → `false` (and `addPane`/`panes` do not occur in the bundle). A true second pane is therefore a **second chart instance** in a second flex cell (`#chartPrice` flex 7, `#chartRsi` flex 3, 6px gap) — not faked.
- **RSI-14, Wilder smoothing**, computed client-side from the closes: 406 points for KEI (420 bars − 14 warm-up), first point 2025-01-07.
- **Confined to 0–100**: `autoscaleInfoProvider` pins the pane range to `{minValue: 0, maxValue: 100}`; observed min 25.49 / max 81.14 (inside range), axis renders `100.00` and `0.00`.
- **30 and 70 drawn**: two dashed price lines on the RSI series (verified objects: prices `[70, 30]`), axis labels `70.00` and `30.00`.
- **Band distinguishable**: a baseline series with `baseValue: {type:"price", price:30}` drawn at value 70 fills the 30–70 zone (`rgba(96,165,250,.17)` → `.05`). It is set on **every price bar timestamp**, which is also what makes the axes line up (see next point).
- **Shared time axis**: both charts report the *identical* visible logical range (276→419 at 1440 for KEI) and pan/zoom mirror both ways through `subscribeVisibleLogicalRangeChange` + `setVisibleLogicalRange`. Without the band carrying all 420 bar times, the RSI series' 14-bar warm-up offset made the two panes drift 14 bars apart — that was found and fixed during this pass.
- Limits that are **not** claimed: the price pane has no time axis of its own (dates live under the RSI pane, TradingView-style); alignment depends on both right price scales having the same width (pinned to `minimumWidth: 76` and equalized at runtime by `_equalizePaneScales()`); the **crosshair is per-pane** — v4 has no cross-pane crosshair link, so hovering the price pane does not draw a line in the RSI pane.

## 4. Verification evidence

### 4.1 Eval (`tools/ui-audit/eval.mjs`, expr files in `%TEMP%`)

| Field | 1440×900 | 390×844 |
|---|---|---|
| MA series that exist | sma10, ema10, sma20, ema20, ema50, ema200 (6) | same |
| MA series visible by default | sma10, ema20, ema50, ema200 (**4**) | same |
| SMA present / points | yes — sma10 411 pts (first 4286.41 @ 2024-12-31), sma20 401 pts | same |
| RSI series | present, 406 pts | present, 406 pts |
| RSI min / max, inside 0–100 | 25.49 / 81.14, `true` | same |
| RSI scale pinned, band, levels | `true`, band base 30 drawn at 70, levels `[70,30]` | same |
| Panes | `domPanes: 2`, `addPane: false`, `panes(): false`, library `4.1.3` | same |
| Time-axis sync aligned | `true` (price 276→419, rsi 276→419) | `true` |
| Chart height | `#chart` **520px** (price 360 / rsi 154) | `#chart` **340px** (price 234 / rsi 100) |
| Document horizontal overflow | **0px** | **0px** |
| Legend | Price, SMA 10, EMA 10 off, SMA 20 off, EMA 20, EMA 50, EMA 200, RSI 14 30/70 | same |
| Toolbar | `Price / 4 of 6 averages` \| `Averages (4 on)` \| `Hide Patterns (0)` | `… \| Show Patterns (0)` |

Raw files: `tools/ui-audit/out/chart-task/eval-final-1440.json`, `eval-final-390.json` (also `eval-1440.json` / `eval-390.json` from the first run, identical).

Toggle proof (`eval-toggle-390.json`, all by real clicks):
- chips before: `sma10:true, ema10:false, sma20:false, ema20:true, ema50:true, ema200:true`
- click SMA 10 → drawn set becomes `[ema20, ema50, ema200]`, `sma10.options().visible === false`, legend shows `SMA 10 off`, storage `{"sma10":false,…}`
- click EMA 10 → drawn set `[ema10, ema20, ema50, ema200]`, legend shows `EMA 10` (no `off`)
- both clicked back → drawn set and storage restored
- pattern pill: `Show Patterns (0) pressed=false` → click → `Hide Patterns (0) pressed=true` → click → `Show Patterns (0) pressed=false`, storage `nse.showPatterns=0`

Pattern annotations against real data (`eval-pattern-{1440,390}.json`, symbol RELIANCE, 6 stored signals):
- 1440: `pill = "Hide Patterns (6)"`, `aria-pressed=true`, wrapper **without** `is-patterns-hidden` (markers drawn)
- 390: `pill = "Show Patterns (6)"`, `aria-pressed=false`, wrapper `fx-chart-wrap is-patterns-hidden` (markers suppressed, count still shown)

Arithmetic cross-check of the client-side line values (independent Python over the API payload): `py SMA10 = 5709.45` == readout `s10 5709.45`; `py EMA20/50/200 = 5512.91 / 5330.86 / 4830.49` == the API's own `ema20/50/200` and == the readout values. So the SMA is right and the readout maps to the right series.

### 4.2 Screenshots (viewed with `read_image`)

- `tools/ui-audit/out/chart-task/ma-1440.png` (KEI, 1440×900) — I see: toolbar `Price / 4 of 6 averages`, `Averages (4 on)`, `Hide Patterns (0)`; price pane with exactly four lines (cyan dashed SMA 10, amber EMA 20, violet EMA 50, slate EMA 200) plus candles, none clipped (headroom above the highest candle, `6000.00` label clear); the hover readout `2026-08-21 O5700.00 H5744.00 L5492.60 C5527.60 RSI 53.5 s105709.45 e205512.91 e505330.86 e2004830.49`; directly below it the **RSI pane with a clearly shaded 30–70 band**, dashed 30/70 lines, labels `70.00`, `53.54`, `30.00`, `100.00`, `0.00`; the shared date axis (Feb–Aug) sits under the RSI pane; legend row of 8 items with `EMA 10 off` and `SMA 20 off` dimmed.
- `tools/ui-audit/out/chart-task/ma-390.png` (KEI, 390×844) — same structure in two stacked panes that fit with no horizontal scroll, `#chart` = 340px; readout `2026-08-21 C5527.60 RSI 53.5`; band and 30/70 lines visible; legend wraps to two rows.
- `pattern-1440.png`, `pattern-390.png` (RELIANCE, 6 signals) — markers drawn with labels at 1440; at 390 the pill reads `Show Patterns (6)` and **no marker text appears on the canvas** (no mobile regression). Crops `pattern-edge-crop.png`, `readout-crop.png`, `audit-390-chart-crop.png`.
- `tools/ui-audit/out/chart-task/375x812-research.png`, `390x844-research.png` are the audit's own full-page captures.

### 4.3 Audit

```
viewport   route          overflowPx  offenders  pageLvl  badWrap  textOut  status  screenshot
375x812    #research      0           755        0        0        0        PASS
390x844    #research      0           755        0        0        0        PASS
summary: 2/2 viewport-routes clean; mobileOverflowFailures=0; worstPageOverflowPx=0
```
(`--settle 6000`, `--out tools/ui-audit/out/chart-task` so no other teammate's run is clobbered.)

### 4.4 Other gates

- `node --check terminal/static/app.js` → exit 0.
- `test_*.py` → **9/9 PASS** (`backtest_integrity`, `data_sources`, `fundamentals_integrity`, `kite_import`, `kite_reconcile`, `ml_integrity`, `research_cockpit`, `scanx_import`, `sizing_safety`).

## 5. What I left out, and why

- **Backend SMA/RSI** — `terminal_api.py` returned no such keys and another writer owned it; client-side derivation avoids any API-contract risk.
- **Cross-pane crosshair sync** — v4.1.3 has no API for it; adding a `setCrosshairPosition` round-trip would be unverifiable in this harness (no synthetic hover), so it was not shipped rather than shipped unverified.
- **More averages / Bollinger / volume pane** — contradicts "fewer, well-spaced lines"; 6 series exist, 4 draw.
- **Empty-state UI for a symbol-less chart** — the `#research` route (no symbol) renders two empty panes; that state is pre-existing and the fix would mean adding markup outside my scope. Noted instead (§6).

## 6. Claims I could NOT verify (plainly)

1. **Cross-pane crosshair** — not implemented, therefore not verified.
2. **Real touch gestures** (finger drag/pinch on the two panes) — only programmatic pan/zoom mirroring and identical logical ranges were verified, in headless Chrome. No physical device.
3. **Intermediate breakpoints** (620/768/950 px) — screenshots and evals cover 390 and 1440 only; the audit covers 375/390.
4. **SMA 20 / EMA 10 rendered appearance** — verified as series state, legend text and storage when toggled on; no screenshot with them ON.
5. **Labelled pattern markers away from the live edge** — every stored signal I could find (RELIANCE: 6, all dated 2026-09-09) is *newer* than the last stored price bar (2026-08-21), so all markers land on the live edge and cluster there. I therefore could not observe an older, mid-chart labelled marker to confirm the label path visually; only its code path and the suppression rule were verified.
6. **Marker clustering at the live edge** — a real, remaining cosmetic defect: the 6 RELIANCE markers stack vertically on the last bar because their dates are beyond the stored price history (data staleness, not chart code). Shapes render correctly; text is now suppressed there instead of being painted clipped into the price-scale gutter. Root cause is outside my write scope.
7. **Mobile sticky header overlap** — at some scroll offsets the app's sticky header (`.fx-topbar`, ~248px on a 390px phone) covers the panel subtitle and, at other offsets, the toolbar. Visible in the screenshots; it is an app-shell behaviour owned elsewhere, and `index.html` is read-only for me.
8. **`#research` with no symbol** — the chart is blank (no data is loaded), which is why the audit's own screenshot of that route shows an empty pane. Pre-existing; unchanged.

## 7. Artifact index

Code: `terminal/static/app.js` (`MA_DEFS`, `_sma`, `_maVisibleMap`/`_setMaVisible`, `_maDrawn`, `_renderChartChrome`, `_setChartData`, `resetChart`, `_applyMarkersToSeries`), `terminal/static/fintech.css` (sections 20–21 appended: two-pane flex box, readout, MA chips, SMA/off swatches).
Evidence: `tools/ui-audit/out/chart-task/` → `eval-final-1440.json`, `eval-final-390.json`, `eval-toggle-390.json`, `eval-pattern-1440.json`, `eval-pattern-390.json`, `ma-1440.png`, `ma-390.png`, `pattern-1440.png`, `pattern-390.png`, `375x812-research.png`, `390x844-research.png`, `*-crop.png`.
