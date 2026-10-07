# tools/ui-audit — headless-Chrome mobile layout audit

Dependency-free verification harness for the NSE Research terminal. It drives the
**real** Chrome over the DevTools Protocol (CDP) and measures the **actually
rendered** page — not a static HTML guess. Node builtins only
(`node:http`, `node:net`, `node:fs`, `node:os`, `node:path`,
`node:child_process`) plus the Node 22+ global `WebSocket`. **No npm install, no
network required** (except the page's own third-party fonts/CDN, see
`--block-external`).

Measured Chrome: `Chrome/154.0.8037.93`, Node `v24.18.1`, Windows.

---

## 1. Start the app

```powershell
# from the repo root: C:\Users\Ankit\Desktop\nse_system
node tools/ui-audit/serve.mjs
```

This spawns `.\env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8011`,
polls `http://127.0.0.1:8011/api/health` (no auth, max 40 s) and then stays in
the foreground until Ctrl+C. If 8011 is busy it automatically picks a free port
and prints the exact audit command to run. It also writes
`tools/ui-audit/out/server.json` with `{ host, port, url, pid }`.

Equivalent manual server (no helper):

```powershell
.\env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8011
```

> The API has no login gate (the HTTP Basic layer was removed from
> `terminal_api.py`), so the harness sends no credentials by default. If a
> target is ever gated again, set both `ADMIN_USER` and `ADMIN_PASS` (or
> `--user`/`--pass`) and the header is sent via `Network.setExtraHTTPHeaders`.

## 2. Run the audit

```powershell
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8011
```

Self-contained variant (starts and stops uvicorn itself):

```powershell
node tools/ui-audit/audit.mjs --spawn-server
```

Other useful options:

```powershell
# one viewport, verbose, offline-safe (blocks unpkg/fonts CDNs)
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8011 --viewports 375x812 --verbose --block-external

# extra routes once the Lead adds hash views
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8011 --routes research,traders,league

# strict mode: also fail when a label paints outside its own box at 375/390
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8011 --fail-on-text-overflow

# optional: only if a target is gated again (both halves are required)
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8011 --user <user> --pass <pw>
```

Full option list: `node tools/ui-audit/audit.mjs --help`.

## 3. Deep-dive one element (justify a verdict)

```powershell
node tools/ui-audit/probe.mjs --url http://127.0.0.1:8011 --selector "#compareRunBtn" --viewport 375x812 --requests
```

Prints the raw geometry for a selector: bounding box, `clientWidth/scrollWidth`,
computed `white-space` / `word-break` / `overflow-wrap` / `flex`, every text line
box (`Range.getClientRects`) with the per-word visual-line count, and the ancestor
chain with each ancestor's width / `overflow-x`. Use it when a report row is
surprising.

---

## What PASS / FAIL means

| Output | Meaning |
| --- | --- |
| `overflowPx` | `document.documentElement.scrollWidth - clientWidth`. **> 0 means the page itself scrolls sideways** — the primary failure. |
| `offenders` | Count of visible elements with `rect.right > viewportWidth + 1` **or** `scrollWidth > clientWidth + 1` while `overflow-x: visible`. Capped list of 25 in `report.json`, worst first. |
| `pageLvl` | Offenders whose ancestors do **not** clip or scroll them. These are the ones that actually cause page-level breakage; `offenders` also counts legit children of a horizontally scrollable table wrapper. |
| `badWrap` | Elements containing a word that is broken across multiple visual lines (measured with `Range.getClientRects()` per word — real geometry, not a guess). Reported with the word, line count and cause (`word-break: break-all`, `overflow-wrap: anywhere`, or `unbreakable-token`). |
| `textOut` | Labels whose painted text extends past their own border box — compared as `Range.getClientRects()` of the element's direct text nodes vs its `getBoundingClientRect()`. Show as `visible/clipped` when an ancestor clips some of them. **This is what catches flex-shrunk `white-space: nowrap` labels colliding with their neighbours**, which produces no document overflow at all. A `*` after `PASS` means such labels exist at that viewport. |
| `status` | `PASS` = `overflowPx == 0`; `FAIL` = `overflowPx > 0` at a width listed in `--fail-widths` (default **375** and **390**, the run's exit-code gate); `warn` = overflow at a non-gated width; `ERROR` = measurement could not be taken. |

**Exit code:** `1` if any viewport in `--fail-widths` (default 375 px and 390 px)
has `horizontalOverflowPx > 0` **or** a failed measurement; `0` otherwise;
`2` on a harness error (Chrome/CDP/server problem). Adding
`--fail-on-text-overflow` also fails the run when a gated viewport has visible
`textOut` entries.

`pageLvl > 0`, `badWrap > 0` and `textOut > 0` are reported but do **not** by
themselves fail the default run — the gate is document-level horizontal
overflow, per the task spec. Use `--fail-on-text-overflow` (strict) when the
overhaul should also be held to label-collision cleanliness.

## Output files (`tools/ui-audit/out/`)

| File | Contents |
| --- | --- |
| `report.json` | Rewritten after every viewport-route. Full measurement per row: `measurement` (in-page geometry), `layoutMetrics` (independent CDP `Page.getLayoutMetrics` cross-check), `loadEventFired`, `networkIdle`, `requestsDuringSettle`, `screenshot`, `errors`, plus a `summary`. |
| `<W>x<H>-<route>.png` | **Full-page** screenshot (`captureBeyondViewport: true`). Can be >19 000 px tall — too big for inline preview, open it in an image viewer. |
| `<W>x<H>-<route>-fold.png` | Viewport-only screenshot of the first screen — small, safe to preview/share. |
| `server.json` | Port/pid chosen by `serve.mjs` (written only when the helper starts the server). |

## How it works (and the limits)

1. `serve.mjs` / `--spawn-server` ensures uvicorn is up.
2. `audit.mjs` picks a free debug port, launches Chrome with
   `--headless=new --disable-gpu --no-first-run --no-default-browser-check
   --hide-scrollbars --remote-debugging-port=<free> --user-data-dir=<temp>`,
   and waits for `/json/version` before connecting the WebSocket.
3. It creates a page target, attaches with `flatten: true`, enables
   `Page`/`Runtime`/`Network`, sets `Cache-Control: no-cache` (plus the
   optional Basic-auth header when credentials are configured).
4. Per viewport: `Emulation.setDeviceMetricsOverride(width, height,
   deviceScaleFactor: 1, mobile: width < 768)` (falls back to the
   `Page.setDeviceMetricsOverride` alias if needed) → `Page.navigate` (with a
   cache-busting `?_audit=N` query so `Page.loadEventFired` really fires on
   every hash route) → wait for `loadEventFired` → wait for network idle (or the
   `--settle` cap) → `Runtime.evaluate` of the in-page measurement function →
   `Page.getLayoutMetrics` cross-check → two screenshots.
5. A navigation that never fires `loadEventFired`, or that renders an empty
   document (no `nav#navRail` / `main`, `bodyChildCount <= 1`, < 40 chars of
   visible text), is **retried once** and, if it still fails, is reported as
   `load-timeout` / `blank-page` and counts as a failure at a gated width. An
   empty page would otherwise trivially "pass" the `scrollWidth` gate.
6. Cleanup: `Browser.close`, `child.kill()`, and on Windows
   `taskkill /PID <pid> /T /F` if Chrome survives; the temp profile dir is
   removed (unless `--keep-profile`).

Known limits:

* One navigation in roughly five was observed to come back blank (no
  `loadEventFired`) — a Chrome/CDP race, not an app bug. The retry + blank-page
  guard above covers it; check `navAttempts` in `report.json` if a run looks odd.
* `networkIdle` is frequently `false`: the terminal keeps a few requests open /
  trickling past the 2.5 s window, so the measurement happens after the fixed
  settle delay. The page is fully loaded (`loadEventFired=true`) either way.
* Third-party assets (`unpkg.com`, `fonts.googleapis.com`) are fetched when the
  machine is online. Use `--block-external` for a repeatable offline run; charts
  powered by the blocked CDN will then not render.
* Screenshots use `captureBeyondViewport`, so very long pages produce very tall
  PNGs (`-fold.png` is the previewable variant).
* Only hash routes are audited (`#research`, …). Any layout that only appears
  after a click (opening a drawer/dialog, selecting a symbol) is **not** covered
  until it is added as a route or driven explicitly.
* `word-break: break-all` / `overflow-wrap: anywhere` inside a narrow container
  is reported as a break even when it is intentional; check `cause` and use
  `probe.mjs` before treating it as a bug.
* `textOut` compares painted text against the element's own border box, so a
  deliberately overflowing label (a "peek" affordance) is reported too. Check
  `ancestorClipped` / `whiteSpace` and confirm the real overlap with
  `probe.mjs`. Verified true positives at 375 px: all 8 `nav#navRail .nav-btn`
  labels are flex-shrunk to a 37.9 px box while `white-space: nowrap` text paints
  8.9–58.5 px past it, so neighbouring labels overlap.
