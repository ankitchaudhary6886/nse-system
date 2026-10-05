---
name: nse-terminal-trader-method
description: Use when adding, editing, auditing, or registering a trading-book method under traders/ — enforces owner rules R30/R35/R38/R40/R41/R42/R43/R44/R45, the duck-typed plugin contract, and the League replay obligation that follows any trader code change.
---

# NSE Terminal — Trader / Book Method Work

The `traders/` library holds **14 registered books, 153 methods**. Each book is
one module with a duck-typed contract. Read the rules before touching one.

## 1. The contract (duck-typed; `traders/base.py` has no base class)

Every module declares, at module level:

```python
SLUG    = "author_slug"          # unique; becomes the League player id and code-hash key
NAME    = "Author Name"
PILLAR  = "swing" | "funda" | "multi"
SOURCE  = "Book Title (Year)"
METHODS = [{"id": ..., "name": ..., "description": ...,
            "direction": "BULLISH"|"BEARISH"|"both", ...}]
def scan(conn=None, limit=800, symbols=None) -> list[dict]: ...
```

`scan` opens its own connection when `conn is None` and must close it. Per-symbol
errors are logged and skipped, never fatal.

Optional hooks the League replay relies on: `_scan_symbol(sym, df)`,
`_load_df(conn, sym, limit=...)` (its default is introspected), `MIN_BARS`,
`MIN_PRICE`.

**Signal shape** (canonical: `traders/mcallen.py:339-352`):
```python
{"symbol", "trader": SLUG, "method", "direction", "signal_type",
 "entry", "stop", "target", "confidence", "notes", "raw",
 "overlaps_with": [...]}   # optional, R41
```

Register in `traders/__init__.py` — it is an **explicit import list**, not
auto-discovery. `traders/wisdom.py` is a 15th file but is **not a trader** (it is
`AXIOMS` + `WISDOM` reference data); do not add it to the registry.

## 2. The rules, and what each actually requires

| Rule | Requirement |
|---|---|
| **R30** | **Setup identification only.** No execution, stop-loss placement, sizing, or trailing logic in trader code. The book's exit philosophy goes into prose (`EXIT_LOGIC.md`). Turtle methods ship `stop=None` because of this. |
| **R35** | Bug safety: ship `_fmt_num` + `_try_emit` so one bad symbol cannot kill a scan. |
| **R38/R40** | Structured exits on every signal, in `raw.exits`. R38 shape = `{price, condition}` (only `nison.py`). **R40 is current**: six blocks — `stop_out`, `target`, `offset`, `invalidation`, `exhaustion`, `time_exit` — each with `thesis` + `hard_number` + `condition`. **Exits are SUGGESTIVE, not directive.** |
| **R41** | Overlap policy: **mark, don't prune.** Add `overlaps_with=[...]`; never consolidate or delete either method. |
| **R42** | **No proxies, no parameter tweaks.** Compute each indicator inline with the book's exact parameters. A missing field means the method ships complete and **silent** (zero signals) until the owner supplies data via `DATA_REQUESTS.md`. |
| **R43** | Emit both `LONG_ENTRY` and `TOP_WARNING`. Warnings are informational reviews of existing positions. **No shorting.** |
| **R44** | Add the trader's section to `EXIT_LOGIC.md`. |
| **R45** | Add the wisdom artifact; fold it into `MARKET_WISDOM.md` (`traders/wisdom.py` mirrors it). |
| **R19** | The system identifies; the owner decides. |
| **R47** | Git + VM steps as whole copy-paste blocks (see `nse-terminal-deploy`). |

## 3. Current coverage (know before you edit)

Registered players: `john_crane` (13), `larry_spears` (7), `oshaughnessy` (19),
`quantitative_value` (20), `value_investing_made_easy` (21),
`way_of_the_turtle` (9), `seven_simple_strategies` (11), `apurva_parikh` (1),
`ishaan_agnihotri` (5), `nison` (6), `chande` (5), `oneil` (7), `mcallen` (11),
`singhal` (18).

Structured `raw.exits`: **nison** (R38), **chande / oneil / mcallen / singhal** (R40).
Setup-only / no exit code: john_crane, larry_spears, way_of_the_turtle,
seven_simple_strategies, ishaan_agnihotri, oshaughnessy, quantitative_value,
value_investing_made_easy. `apurva_parikh` is a hybrid (shared `EXIT_RULES` dict).

**Doc drift to correct when you touch these** — `EXIT_LOGIC.md` claims exit blocks
for `oshaughnessy`, `quantitative_value`, `value_investing_made_easy` and
`apurva_parikh` that do not exist in the code (F-25).

The `"scan": true/false` key inside `METHODS` is **declarative only** — nothing
reads it. Real tradability comes from `trader_league.classify()`.

## 4. Registration and the League obligation

Registering a book or changing its code changes `_code_hash(slug)` — a
`sha1[:12]` of `traders/<slug>.py`. For `home` it hashes
`strategy_config.SETUP` + `.SCREENER` + the bytes of `setup.py` + `scanner.py`.

Therefore **any** of these triggers a mandatory replay:
- editing any `traders/*.py`
- changing `strategy_config.SETUP` or `.SCREENER`
- editing `setup.py` or `scanner.py`

```bash
cd ~/nse-system
git pull
sudo systemctl restart nse-terminal
source venv/bin/activate
python trader_league.py selftest          # must print 28/28
python trader_league.py status            # look for `code changed`
python trader_league.py replay --changed --background
```
Expected: `Code/settings changed for: <slugs>` (or `nothing to redo`). Then
re-run `status` until no `code changed` flag remains.

## 5. Common bugs seen in this library

- **Method shadowing.** `singhal.py` had two functions named `_detect_vcp`; the
  later method definition shadowed the helper, so VCP **never emitted a signal**.
  Any two same-named top-level functions in one module is a red flag.
- **Undefined names in comprehensions.** `larry_spears._ma_trend` referenced an
  undefined `v` in an inline `all(...)`. Fixed with
  `_strictly_increasing`/`_strictly_decreasing` helpers.
- **Off-by-one in window indexing.** `setup.py` v3.1 produced a 10-3000 %
  impulse instead of 35.1-46.8 % from a slice bug. When a method emits wildly
  out-of-range values, suspect the slice, not the thresholds.

## 6. Checklist before shipping a trader change

- [ ] `SLUG`/`NAME`/`PILLAR`/`SOURCE`/`METHODS` present; registered in `__init__.py`.
- [ ] `_fmt_num` + `_try_emit` used; a bad symbol cannot abort the scan.
- [ ] Setup-only (R30); no stop/size/trailing logic added.
- [ ] Indicators inline with the book's exact parameters (R42); no proxy fields.
- [ ] `raw.exits` in R40 shape with `thesis` + `hard_number` + `condition`.
- [ ] `overlaps_with` populated where methods echo each other (R41).
- [ ] `LONG_ENTRY` vs `TOP_WARNING` correct (R43); no shorts.
- [ ] `EXIT_LOGIC.md` section added (R44); wisdom artifact added (R45).
- [ ] `python -c "import traders; [t['slug'] for t in traders.list_traders()]"` lists the book.
- [ ] `trader_league.py selftest` → 28/28, then `replay --changed --background`.
- [ ] No two top-level functions share a name in the module.
