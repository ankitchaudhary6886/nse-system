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
- **Same exits for all** = setup stop (or 2×ATR), 2R target, 20-day time stop. Makes entry approaches more comparable, while actual fills and portfolio capacity still affect results.

The **Signal Genome** groups closed trades by playbook, method, and market
regime. It surfaces the strongest and weakest historical contexts with at
least 10 shared-exit trades, and places each book-exit result beside it. This
is retrospective analysis, not a forecast or causal test; small samples and
the survivorship/fundamentals limitations below still apply.

---

## 2. First time — copy-paste blocks

Every block is complete on its own: paste the **whole** block, let it
finish, then compare with **You should see**. If you see something else
(or any `Traceback`), stop and send the output.

**Block A — Laptop (PowerShell): connect to the VM**
```
ssh -i C:\Users\Ankit\.ssh\nse.pem ubuntu@140.238.226.249
```
You should see: a prompt like `ubuntu@...:~$`. Paste all VM blocks there.

**Block B — VM: get the new code and restart the terminal**
```
cd ~/nse-system
git pull
sudo systemctl restart nse-terminal
sleep 20
sudo systemctl status nse-terminal --no-pager | head -5
sudo journalctl -u nse-terminal --since "3 min ago" --no-pager | grep -o "league@Mon-Fri19:00, leagueCard@Sat11:00"
```
You should see: `git pull` listing the changed files (or `Already up to date.`),
`Active: active (running)`, and as the last line
`league@Mon-Fri19:00, leagueCard@Sat11:00` (the two league jobs are scheduled).
If that last line is missing, the terminal was still starting — wait 30 seconds and paste:
```
sudo journalctl -u nse-terminal --since "5 min ago" --no-pager | grep -o "league@Mon-Fri19:00, leagueCard@Sat11:00"
```

**Block C — VM: check the accounting (a few seconds, no data needed)**
```
cd ~/nse-system
source venv/bin/activate
python trader_league.py selftest
```
You should see as the last line: `26/26 checks passed`. If any line says FAIL, stop and send it.

**Block D — VM: start the pre-season replay (runs in the background)**
```
cd ~/nse-system
source venv/bin/activate
python trader_league.py replay --years 3 --symbols 300 --background
```
You should see:
```
Replay started in the background (pid 12345, 3 years, 300 stocks).
You can close SSH now — it keeps running.
```
Same as the button in the terminal: **🏆 League → ⚙️ Pre-season replay → ▶ Start**.
Only one replay can run at a time — a second start just says `Not started: a replay is already running`.

⏱ Time: about 1–1.5 hours on a fast core (300 stocks × 3 years); the free VM can take 2–4 hours.
It is **resumable**: if it stops (restart, reboot), paste Block D again and it continues where it
stopped. Later runs only add the new days.

**Block E — VM: check progress (any time)**
```
cd ~/nse-system
source venv/bin/activate
python trader_league.py status
tail -3 data/logs/league_replay.out
```
You should see: `Replay running (pid …)` under the table, and progress lines like
`[ 40%] 480/1200 stocks · 61,204 signals · 38m10s elapsed · ETA 57m15s`.
When it has finished, the last lines show the `VERDICT:` and `Replay running` is gone.

**Block F — VM: read the verdict (after the replay finished)**
```
cd ~/nse-system
source venv/bin/activate
python trader_league.py ready
python trader_league.py table
python trader_league.py table --exit common
python trader_league.py player home
```
You should see: the real-money checklist ending in `VERDICT: READY`, `PAPER FIRST` or
`NOT READY`, then the league table with book exits, the table with the same exits for all,
and our system's full report. The **🏆 League** tab shows the same.

**Block G — VM: stop the replay (only if you must)**
```
pkill -f "trader_league.py replay"
```
You should see: nothing. Block E no longer shows `Replay running`. Block D continues later
from where it stopped.

**Then — nothing.** The live league starts by itself at 19:00 IST on the next weekday.
First trades appear the day after the first run.

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
| **Signal Genome** | Closed-trade results split by playbook, method, and market mood; shared-exit N is shown | Look for enough trades and consistency under both exit modes |

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
- 🔴 **NOT READY** — the verdict line lists what failed. Change ONE thing in `strategy_config.py`
  on the laptop, push it, then run the matching block on the VM and compare.

**Block H — VM: after changing exit / sizing / cost settings** (`BACKTEST` or `LEAGUE`) — seconds,
the stored signals are re-traded:
```
cd ~/nse-system
git pull
sudo systemctl restart nse-terminal
source venv/bin/activate
python trader_league.py backtest
```
You should see: the checklist and the new `VERDICT:` line.

**Block I — VM: after changing signal settings** (`SETUP` or `SCREENER`, or any trader's code) —
those change the signals themselves, so only the changed players are replayed again:
```
cd ~/nse-system
git pull
sudo systemctl restart nse-terminal
source venv/bin/activate
python trader_league.py replay --changed --background
```
You should see: `Code/settings changed for: …` naming what you changed (e.g. `home` = our
system), then `Replay started in the background …`. Watch it with Block E; it simulates by
itself at the end. (`nothing to redo` means no signal setting or trader code changed — use Block H.)

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

The simulator is checked by `python trader_league.py selftest` (28 checks:
costs, gaps, sizing, caps, time stops, trailing stops, partial exits, O'Neil's
8-week rule, equity reconciliation, shared-vs-book genome aggregation, and a
"no peeking" replay test).

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
| "No backtest yet" | Start the replay — Block D |
| ⚠ next to a player in the replay table | That trader's code or settings changed after its replay — Block I |
| Replay stopped after `systemctl restart` | Normal (a restart stops child jobs) — Block D again, it resumes |
| VM too slow | Block G, then Block J (fewer stocks; add more later — only new stocks are replayed) |
| Live table all ₹10,00,000 | Normal on day 1 — orders fill the next trading day |
| Disk space | Replay signals take ~100–150 MB for 300 stocks × 3 years (table `league_signals`) |
| Scorecard not on Telegram | Block K shows the text; Telegram creds as in §3 of the handoff |

**Block J — VM: lighter replay for a slow VM**
```
cd ~/nse-system
source venv/bin/activate
python trader_league.py replay --years 3 --symbols 150 --background
```
You should see: `Replay started in the background (pid …, 3 years, 150 stocks).`

**Block K — VM: print the weekly scorecard without sending it**
```
cd ~/nse-system
source venv/bin/activate
python trader_league.py scorecard --print
```
You should see: the league table text that Telegram gets every Saturday 11:00 IST
(`No league run yet.` until the first run).
