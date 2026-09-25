# 🏆 TRADER LEAGUE — test the system before real money

**One line:** the 14 famous-trader books and **our system** each get
₹10,00,000 of play money. They trade their own signals on real NSE data,
after every Indian cost. The league answers one question honestly:
**is our system ready for real money?**

- Engine: `trader_league.py` · Tab: **🏆 League** · API: `/api/league/*`
- Settings: `strategy_config.LEAGUE` · Log: `data/logs/league.log`

---

## 1. What it does (30 seconds)

| Part | What happens | When |
|---|---|---|
| **Backtest ("pre-season")** | Replays every past trading day. On each day every book sees ONLY the prices known that day (no peeking), and its buy signals are stored. Then ₹10 lakh portfolios trade those signals. | Once (you start it), a few hours, resumable |
| **Live league** | Every weekday evening the scheduler stores today's signals from all 14 books + our Swing Desk and re-simulates the paper portfolios from the league start. | Mon–Fri 19:00 IST, automatic |
| **Scorecard** | League table + our system's rank on Telegram. | Saturday 11:00 IST |

Two scoreboards:
- **Book exits** = each book's own exit rules (Turtle trails the 10/20-day low, O'Neil cuts at 8%, …).
- **Same exits for all** = setup stop (or 2×ATR), 2R target, 20-day time stop. Compares **entries only**.

---

## 2. First time (on the VM) — copy-paste

**Step 1 — deploy** (laptop pushes, then on the VM):
```
cd ~/nse-system && git pull
sudo systemctl restart nse-terminal
```

**Step 2 — check the accounting** (no database needed, takes 2 seconds):
```
cd ~/nse-system && source venv/bin/activate
python trader_league.py selftest
```
Expected last line: `26/26 checks passed`. If any check says FAIL, stop and report it.

**Step 3 — start the pre-season replay.** Easiest: open the terminal → **🏆 League**
→ **⚙️ Pre-season replay** → **▶ Start / continue replay** (defaults: 3 years, 300 stocks,
1 core). It runs in the background at low priority; you can close the page.

Same thing from SSH (keeps running after you disconnect):
```
nohup python trader_league.py replay --years 3 --symbols 300 > data/logs/league_replay.out 2>&1 &
```
Check progress any time:
```
python trader_league.py status
tail -3 data/logs/league_replay.out
```
Expected progress lines look like:
`[ 40%] 480/1200 stocks · 61,204 signals · 38m10s elapsed · ETA 57m`

⏱ Time: about 1–1.5 hours for 300 stocks × 3 years on one fast core (the 10
chart books take ~2 ms per stock per day each); a free-tier VM can take 2–4 hours. It is **resumable**: if it stops (restart, reboot), press
Start again and it continues where it stopped. Later runs only add new days.

**Step 4 — read the verdict.** When the replay finishes it simulates automatically.
Open **🏆 League** or run:
```
python trader_league.py ready
python trader_league.py table
python trader_league.py table --mode backtest --exit common
python trader_league.py player home
```

**Step 5 — nothing.** The live league starts by itself at 19:00 IST on the next
weekday. First trades appear the day after the first run.

---

## 3. How to read the numbers

| Number | Plain meaning | Good sign |
|---|---|---|
| **Value / Return** | What ₹10 lakh became, after ALL costs | Above Nifty over the same dates |
| **CAGR** | Yearly growth rate | Beats Nifty's CAGR |
| **Max DD** | Worst fall from a peak | ≤ 25% (could you sit through it?) |
| **PF (profit factor)** | ₹ won per ₹ lost | ≥ 1.3 (below 1.0 loses money) |
| **Win rate** | % of trades that made money | Means little alone — a 35% win rate with big winners is fine |
| **Avg R** | Average result in units of risk (1R = the planned loss) | Above +0.2R |
| **Costs paid** | STT + stamp + charges + slippage | Shows how much trading frequency costs |
| **Bad-luck DD (95%)** | Monte Carlo: trades reshuffled 1,000 times — 95% of orders stay above this drawdown | ≤ 35% |
| **Market mood** | Results split by regime at entry (STRONG_BULL … CAPITULATION) | Tells you WHEN the method works |

---

## 4. The real-money checklist

| Check | Bar | Why |
|---|---|---|
| Enough trades | ≥ 50 | Fewer = could be luck |
| Profit factor after costs | ≥ 1.3 | Edge must survive STT + slippage |
| Worst fall (max drawdown) | ≤ 25% | Survivable in real life |
| Beats Nifty buy-and-hold | higher CAGR | Otherwise an index fund is less work |
| Profitable in most years | ≥ 60% of years | One lucky year must not carry it |
| Bad-luck test (Monte Carlo) | ≤ 35% | Bad trade order won't wipe you out |
| Survives worst-case fills | PF ≥ 1.0 | Re-run assuming the stop always came first on busy days |
| Live paper trading confirms it | ≥ 30 trades, PF ≥ 1.0 | The future must agree with the past |

**Verdicts**
- 🟢 **READY** — every check passes. Start with **25% of planned capital**, scale up after 3 good months.
- 🟡 **PAPER FIRST** — backtest passes, but fewer than 30 live paper trades. Keep watching the live league.
- 🔴 **NOT READY** — the verdict line lists what failed. Change one thing in `strategy_config.py`, re-run
  `python trader_league.py backtest` (seconds — signals are stored), compare. Changing SETUP / SCREENER
  values changes the signals themselves → run `python trader_league.py replay --players home --fresh`.

---

## 5. How realistic is the simulation?

| Topic | What the league does |
|---|---|
| Entry | Signal at the close → order for the **next day**. Buy-stop fills at the trigger, or at the open if it gaps above. Orders expire after 3 days. |
| Stops | A gap below the stop fills **at the open** (worse than the stop), exactly like real life. |
| Same-day high/low | Daily bars don't show which came first. Default: green candle = open→low→high→close, red = open→high→low→close. The checklist also re-runs everything with "stop always first". |
| Sizing | 1% of equity at risk per trade (× regime size for our system), max 20% in one stock, max 10 stocks, cash never negative, position ≤ 5% of the stock's average daily value. |
| Costs (delivery) | STT 0.1% buy + sell · stamp 0.015% buy · NSE 0.00297% · SEBI ₹10/cr · GST 18% on charges · DP ₹15.93 per sell · brokerage ₹0 (set `BROKERAGE_PER_ORDER` if yours isn't) |
| Slippage | 0.2% per side (small/mid caps) |
| Tradeable | Price ≥ ₹20 and average daily value ≥ ₹1 crore **on the signal day** |
| Our system | Same pipeline as the Swing Desk, day by day: regime (^NSEI) → breadth → sector top-3 → Stage-2 screener → Gabani SetupDetector → fresh pattern only. Exits = `strategy_config.BACKTEST` (same as backtest.py). |

The simulator is checked by `python trader_league.py selftest` (26 hand-calculated
cases: costs, gaps, sizing, caps, time stops, trailing stops, partial exits,
O'Neil's 8-week rule, equity reconciliation, and a "no peeking" replay test).

---

## 6. Each book's exit rules (from EXIT_LOGIC.md)

| Player | Exit rules used in "Book exits" |
|---|---|
| Our System | Pattern-day-low stop, +3R target (or tranches if enabled), 30-day time stop |
| John Crane | Swing-low stop, 5-day-low trail, opposite reaction swing exits, 20-session window |
| Larry Spears | 2×ATR safety stop, out on day 5 if not working, 10-day-low trail, opposite setup exits |
| Curtis Faith (Turtle) | 2N stop, exit on the 10-day low (System 1) / 20-day low (others) |
| Patel & Kiri | 2×ATR (or setup) stop, resistance target, close below 9 EMA once in profit |
| Ishaan Agnihotri | Swing-low stop, resistance target, close below 9 EMA once in profit |
| Steve Nison | Candle-low stop, resistance target, 3–10 session setup validity |
| Tushar Chande | 2×ATR stop, method targets, 10-day-low trail after +2R, method time exits |
| William O'Neil | 8% max loss, +20% profit — but +20% within 3 weeks = hold 8 weeks, then 50-DMA trail |
| Fred McAllen | Pattern-low stop, measured-move target, setup windows, top-warning exits |
| Aseem Singhal | Structural stop, ≥ 2R target, 9 EMA trail after +1R, per-method windows |
| 4 fundamentals books | Equal weight, no stops, annual (O'Shaughnessy, QV) or quarterly (Lowe, Parikh) re-check |

---

## 7. Honest limits

1. **Survivorship bias:** the backtest uses today's stock list, so companies that shrank or died are
   missing → backtests look better than reality. That's why live paper trading is part of the verdict.
2. **Fundamentals books** (O'Shaughnessy, Quantitative Value, Lowe, Parikh) and O'Neil's earnings checks
   need historical fundamentals we don't store (DR-01) → live league only.
3. **Our system's fund veto + ALL-WEATHER mode** use today's fundamentals → skipped in the backtest
   (`HOME_USE_FUND_VETO`), used in the live league (it copies the Swing Desk's real signals).
4. **Taxes are not included** (STCG 20% on short-term gains). Results are pre-tax.
5. Benchmark = **^NSEI** from Yahoo (cached in `league_index`); if Yahoo is down it falls back to index
   rows in prices_daily, then to an equal-weight index of our universe.

---

## 8. Troubleshooting

| You see | Do this |
|---|---|
| "No backtest yet" | Start the replay (step 3) |
| ⚠ next to a player in the replay table | That trader's code changed after its replay → `python trader_league.py replay --players SLUG --fresh` |
| Replay stopped after `systemctl restart` | Normal (restart stops child jobs). Press Start again — it resumes |
| VM too slow | Start with `--symbols 150`, add more later (only new stocks are replayed) |
| Live table all ₹10,00,000 | Normal on day 1 — orders fill the next trading day |
| Disk space | Replay signals take ~100–150 MB for 300 stocks × 3 years (table `league_signals`) |
| Scorecard not on Telegram | `python trader_league.py scorecard --print` shows the text; Telegram creds as in §3 of the handoff |
