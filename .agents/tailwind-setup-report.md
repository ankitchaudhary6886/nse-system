# Tailwind / tooling setup report — task-1 (owner: tooling-setup)

Working dir: `C:\Users\Ankit\Desktop\nse_system`
Node v24.18.1 / npm 11.16.0 · Tailwind **v4.3.3** · npm registry **reachable** (default registry, no CDN, no proxying)

---

## 1. npm reachability

```
$ npm view tailwindcss version
4.3.3
EXIT=0
```

Network **was available**. Every dependency below is a **real installed package** — no hand-written
substitutes for a library were needed anywhere.

## 2. Exact versions installed (`npm install`, `npm ls --depth=0`)

| Package | Version | Kind |
|---|---|---|
| `tailwindcss` | 4.3.3 | devDependency |
| `@tailwindcss/cli` | 4.3.3 | devDependency |
| `clsx` | 2.1.1 | dependency (vendored to `static/vendor/`) |
| `tailwind-merge` | 3.7.0 | dependency (vendored to `static/vendor/`) |
| `lucide-static` | 1.52.0 | dependency (icon data vendored to `static/vendor/`) |

36 packages installed, 0 install failures. `package-lock.json` was an empty stub (`"packages": {}`)
and is now a real lockfile (38 526 bytes).

`npm audit`: **4 high** (`@parcel/watcher` → `micromatch` → `braces` stack-exhaustion DoS).
All four are **dev-toolchain only** (the Tailwind CLI's file watcher). Nothing from this chain is
served to the browser; `static/vendor/**` contains only `clsx` / `tailwind-merge` / extracted icon
bodies. Not remediated because `npm audit fix --force` would move off the v4 CLI line.

## 3. Final build command (registered in `package.json`)

```json
"build:css": "tailwindcss -i terminal/static/tailwind.src.css -o terminal/static/tailwind.css --minify",
"watch:css": "tailwindcss -i terminal/static/tailwind.src.css -o terminal/static/tailwind.css --watch=always"
```

`npm run build:css` → `Done in 149ms`, exit 0. Output `terminal/static/tailwind.css` = **2 lines
(minified, avg 1 654 chars/line)**; size grows with the number of utilities in use — 3 304 bytes / 21
rules at first build, 3 348 bytes / 23 rules on the next, and **3 307 bytes / 24 rules** after the
unlayered re-emit (§4b) and two further rebuilds on the Lead's live markup pass. That growth
(6 → 21 → 23 → 24 rules, e.g. `.sticky`, `.resize`, `.collapse` appearing as the Lead edited
`index.html`/`app.js`) is live proof that the `@source` scan set tracks the real markup.

**Watch mode caveat (fixed):** the task draft asked for `--watch`; that flag is wrong in any
non-interactive context. The CLI source disposes the watchers on stdin EOF:

```js
e["--watch"]!=="always"&&process.stdin.on("end",()=>{...process.exit(0)...})
```

so under redirected/closed stdin it exits 0 immediately and never writes the file (verified twice:
`npm run watch:css` returned at once, exit 0, no output written). The CLI's own help text says it:
*"Watch for changes and rebuild as needed, and use `always` to keep watching when stdin is closed."*
`--watch=always` was verified detached under redirected stdin: still alive after 9 s, wrote the
unminified sheet (`Done in 257ms`). The script therefore uses `--watch=always` — the one intentional
deviation from the task text, because the literal form is a no-op in this environment.

## 4. Preflight exclusion — YES, excluded (grep evidence)

`terminal/static/tailwind.src.css` imports **only** the `theme` tokens and the `utilities`
implementation and never `tailwindcss/preflight.css`:

```css
@layer theme;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/utilities.css" source(none);   /* deliberately NOT layer(utilities) - see 4b */
@source "./**/*.html";
@source "./**/*.js";
```

Grep evidence against the compiled `terminal/static/tailwind.css`:

```
task pattern  *,\s*::after,\s*::before  => absent
box-sizing:border-box                   => absent
*,:before,:after universal              => FOUND (1)   <-- see note
@layer base block                       => absent
margin:0                                => absent
padding:0                               => absent
border:0 solid                          => absent
-webkit-text-size-adjust                => absent
tab-size                                => absent
-webkit-tap-highlight-color             => absent
::file-selector-button                  => absent
line-height:inherit                     => absent
font-family:inherit                     => absent
background-color:transparent            => absent
list-style:none                         => absent
text-decoration:inherit                 => absent
```

**Note on the single FOUND universal selector — it is not Preflight.** Tailwind emits a
custom-property initializer for browsers lacking `@property`:

```css
@layer properties{@supports (...) or (...){*,:before,:after,::backdrop{--tw-border-style:solid;
--tw-outline-style:solid;--tw-blur:initial;--tw-brightness:initial;...}}}
```

It declares **only `--tw-*` custom properties** — no `box-sizing`, no `margin`/`padding`, no
`border` shorthand, no `font`/`line-height`, and it lives in the `properties` layer. Every real
Preflight signature (all sixteen probes above) is absent, so the existing `style.css` / `polish.css`
/ `explain.css` element defaults are untouched. The literal pattern from the task
(`*, ::after, ::before`) does **not** appear because v4 minifies to the single-colon `:before`/`:after`.

Also worth recording: the minifier prunes the empty `@layer ...;` order statement and, once
utilities are unlayered (4b), the emitted `@layer` blocks are only `properties` and `theme` — no
`base` layer and no `utilities` layer exist in the output at all.

## 4b. Utilities are emitted UNLAYERED (cascade-layer fix)

Originally the utilities were wrapped in the native cascade layer `@layer utilities`, matching
Tailwind v4's default. That was a real integration bug: `style.css`, `polish.css`, `explain.css` and
`fintech.css` are **unlayered**, and per the cascade-layers spec an unlayered normal declaration beats
**every** layered declaration regardless of specificity or source order — so `.p-4` on a `.card` that
`style.css` already pads would silently lose, and moving the `<link>` later would not help.

Fix applied: `@import "tailwindcss/utilities.css" source(none);` — no `layer(...)`. The utility
classes are now ordinary top-level (unlayered) rules that compete with the legacy sheets by
specificity and source order. The `theme` custom-property block stays layered (as requested) because
it only declares design tokens on `:root`, which nothing competes with. Preflight exclusion is
unaffected — it never depended on the layer.

Fresh evidence after the re-emit:

```
byte size        => 3 307
first 200 chars  => /*! tailwindcss v4.3.3 | MIT License | https://tailwindcss.com */
                    @layer properties{@supports (((-webkit-hyphens:none)) and (not (margin-trim:inline)))
                    or ((-moz-orient:inline)) and (not (color:rgb(fro...    [truncated at 200]
@layer wrappers  => @layer properties | @layer theme        <-- '@layer utilities' GONE
first utility selector (.collapse) at index 825; search for any '@layer' at/after it => NONE
                   => every utility rule is top-level / unlayered
minification     => 2 lines, avg 1 654 chars/line
rules            => 24: .collapse .visible .fixed .relative .sticky .container .block .flex .grid
                    .hidden .inline .table .shrink-0 .resize .flex-wrap .border .bg-sky-500 .px-2
                    .px-4 .py-1 .underline .outline .filter .transition
```

Preflight re-probed after the change: `*, ::after, ::before`, `box-sizing:border-box`,
`@layer base {`, `margin:0`, `padding:0`, `border:0 solid`, `-webkit-text-size-adjust`, `tab-size`,
`line-height:inherit`, `list-style:none` — all still **absent**; the only universal selector remains
the `@layer properties` `--tw-*` initializer.

**Consequence for the Lead:** load `tailwind.css` **last** among the stylesheets. Utilities now win
ties by source order, so being last is what makes them authoritative over equal-specificity legacy
rules; equal-or-higher-specificity legacy selectors still beat them on their own merits, and the `!`
modifier remains available as the escape hatch. If a legacy rule is more specific (e.g. `.panel .card`,
specificity 0,2,0) it will still beat `.p-4` (0,1,0) — that is normal CSS, not a layering artifact.

## 4c. Custom-property inventory (`--fx-*` collision check — none)

The only `:root,:host` token block in the compiled sheet (inside `@layer theme`) declares **6**
custom properties, and **none of them is an `--fx-*` name**. A file-wide search for `--fx-` returns
zero matches, so `terminal/static/tailwind.css` cannot overwrite fintech.css's `--fx-*` tokens:

```
--color-sky-500
--spacing
--radius-sm
--radius-md
--default-transition-duration
--default-transition-timing-function
```

Only these 6 appear because Tailwind v4 tree-shakes unused theme variables — the list grows as more
utility classes enter the scan set (adding e.g. `bg-red-500` adds `--color-red-500`), but every
Tailwind token stays inside Tailwind's own namespaces (`--color-*`, `--spacing*`, `--radius-*`,
`--font-*`, `--text-*`, `--shadow-*`, `--blur-*`, …) and will never be named `--fx-*`.

Two other custom-property sites exist and are equally namespaced away from `--fx-*`:
- `@layer properties` universal selector (`*,:before,:after,::backdrop`) declares 15 Tailwind-internal
  `--tw-*` properties (`--tw-border-style:solid`, `--tw-outline-style:solid`, `--tw-blur:initial`,
  `--tw-brightness`, `--tw-contrast`, `--tw-grayscale`, `--tw-hue-rotate`, `--tw-invert`,
  `--tw-opacity`, `--tw-saturate`, `--tw-sepia`, `--tw-drop-shadow`, `--tw-drop-shadow-color`,
  `--tw-drop-shadow-alpha`, `--tw-drop-shadow-size`).
- 15 `@property` registrations for the same `--tw-*` names at the end of the file.

**Answer: no `--fx-*` collision — safe to load last.**

Scanning is proven live: `.px-2`, `.py-1`, `.bg-sky-500`, `.px-4` in the output are harvested from
the usage example inside `vendor/cn.js`, not from any hand-written CSS.

## 5. Vendored utility status — all real packages

| File | Bytes | Source | Status |
|---|---|---|---|
| `terminal/static/vendor/clsx.js` | 350 | `node_modules/clsx/dist/clsx.mjs` | **REAL PACKAGE**, ESM re-export shim |
| `terminal/static/vendor/tailwind-merge.js` | 545 | `node_modules/tailwind-merge/dist/bundle-mjs.mjs` | **REAL PACKAGE**, ESM re-export shim |
| `terminal/static/vendor/cn.js` | 568 | hand-written glue (4 code lines) | **HAND-WRITTEN GLUE** over the two real packages |
| `terminal/static/vendor/lucide.js` | 5 924 | `node_modules/lucide-static/icons/*.svg` (v1.52.0) | **REAL PACKAGE DATA**, generated; only the `icon()` wrapper is hand-written |
| `terminal/static/vendor/lib/clsx.mjs` | 388 | verbatim copy | **REAL PACKAGE** — SHA-256 identical to upstream (`Get-FileHash` equality = `True`) |
| `terminal/static/vendor/lib/tailwind-merge.mjs` | 109 671 | bundle copy | **REAL PACKAGE** — verbatim except `sourceMappingURL` comment removed + attribution header + `export { twMerge as default }` appended |

Not hand-written: `clsx`, `tailwind-merge`. Hand-written: only the `cn()` composition line and the
`icon()` SVG wrapper (attribute normalization, escaping, `aria` handling). Licenses preserved in the
file headers (clsx MIT, tailwind-merge MIT, lucide ISC).

`icon(name, attrs)` bundles 15 curated icons — `search, refresh-cw, menu, x, chevron-down, info,
line-chart, activity, alert-triangle, trending-up, trending-down, layers, sliders-horizontal,
external-link, check` — all audited programmatically as `width="24" height="24" viewBox="0 0 24 24"
fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
aria-hidden="true"`. No icon markup was hand-drawn: all 15 sets of path data are copied verbatim from
the shipped `node_modules/lucide-static/icons/*.svg` files and only re-wrapped with normalized `<svg>`
attributes. Unknown names return `''` (safe to interpolate). `attrs`
supports `size`, `class`, `strokeWidth`, `fill`, `stroke`, `title` plus pass-through
`data-*`/`aria-*`; a `title`/`aria-label` switches the SVG to `role="img"` + `aria-label` for
accessibility. Attribute names/values are validated and HTML-escaped.

## 6. Acceptance evidence

```
$ node --input-type=module -e "import('./terminal/static/vendor/cn.js').then(m=>console.log(m.cn('a','b')))"
a b
EXIT=0

clsx named: x y | default: x
twMerge named: p-4 | default: px-3 | twJoin: function
all 15 icons: 24x24 + fill=none + stroke=currentColor + stroke-width=2 + aria-hidden + viewBox OK
```

## 7. Caveats the Lead must know

1. **`tailwind.css` is not linked yet.** `terminal/static/index.html` (Lead-owned) still loads only
   `style.css?v=21`, `polish.css?v=2`, `explain.css?v=2`, `fintech.css?v=1`. Add
   `<link rel="stylesheet" href="/static/tailwind.css?v=1">` **as the last stylesheet** to activate the
   sheet — see §4b for why the position now matters. I did not touch that file.
2. **Cascade-layer precedence — RESOLVED by re-emitting utilities unlayered (§4b).** Utilities are
   now ordinary top-level rules, so they compete with the legacy sheets by specificity and source
   order. **Load `tailwind.css` last** so it wins ties at equal specificity; a more specific legacy
   selector (e.g. `.panel .card`) still beats `.p-4` on its own merits, which is normal CSS. Tailwind's
   `!` modifier remains the escape hatch for that case.
3. **Rebuild after adding classes.** The build-time output is only ~3.3 KB because today's markup
   uses few utilities. `npm run build:css` must be re-run after `index.html`/JS changes land, or the
   new classes will be missing from the sheet.
4. **Scan scope is deliberately `terminal/static` only.** `source(none)` keeps builds deterministic
   (no utility names harvested from the ~200 Python sources). `app.py` and `glossary_ui.py` do emit
   HTML strings, so if Tailwind classes are ever written there they will **not** be generated — tell
   me and I will add the matching `@source` lines (I own `tailwind.src.css`). JSON/CSS-only class
   sources (e.g. a Python dict of classes) are invisible to the scanner by design.
5. **`node_modules/` is now in `.gitignore`** (added at line 45, one line, with the Lead's explicit
   grant — `.gitignore` was outside my original scope). `git check-ignore -v node_modules` →
   `.gitignore:45:node_modules/`, and `node_modules/` no longer appears as untracked.
   `terminal/static/vendor/` **is** intended to be committed (it is the runtime dependency).
6. **`"type": "module"` was added to `package.json`.** It is required for the acceptance command to
   load `vendor/*.js` as ESM under Node (without it, `.js` is parsed as CommonJS and `export` is a
   syntax error). Consequence: any future root-level `.js` file is ESM. No root `.js` files exist today.
7. **`@source "./**/*.{html,js}"` does not work** — brace expansion is rejected by the CSS parser
   (`CssSyntaxError: Invalid declaration: 'html,js'`). Written as two globs instead. Separately, note
   that a `*/` sequence inside a CSS or JS block comment terminates the comment early — this bit both
   `tailwind.src.css` and the generated `lucide.js` during development and is why comments avoid `**/`.
8. **`@parcel/watcher`'s install script was skipped** by npm's allow-scripts policy
   (`npm warn allow-scripts @parcel/watcher@2.5.1 (install: node scripts/build-from-source.js)`).
   Harmless: the prebuilt native `watcher.node` (518 144 bytes) is present and watch mode was verified
   working. No action needed unless a non-x64/non-Windows platform is targeted.
9. **Scope compliance.** `git status --porcelain` after my work shows my writes only as
   `M .gitignore` (one granted line: `node_modules/`), `M package-lock.json`,
   `?? .agents/tailwind-setup-report.md`, `?? package.json`,
   `?? terminal/static/{build.config.json,tailwind.css,tailwind.src.css,vendor/}`.
   The other modified files (`index.html`, `app.js`, `cards.js`, `deployment.js`, `ideals.js`,
   `research.js`, `fintech.css`, `tools/`) belong to other writers and were **not** touched or
   reformatted by me. No repo-wide formatter was run.
