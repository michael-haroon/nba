# Trading System

Automated pre-game trading on Kalshi NBA markets using ensemble ML predictions.

---

## Core Philosophy

**We only have edge before tipoff.** Every feature in our models (rolling stats, ratings, rest days) is knowable before the game starts. After tipoff, in-game price movement reflects information we cannot predict. Therefore:

- All positions are entered pre-game
- We never adjust based on live game state
- The maker strategy exits before tipoff; hybrid holds aligned positions through settlement

**Diversity over concentration.** A single game produces 100+ tradeable markets (winner, spread ladder, totals, first-half). We spread capital across uncorrelated dimensions rather than loading up on one bet.

**The model knows what it doesn't know.** Tail predictions (spread > 13) are systematically overconfident (3-8% bias from QQ analysis). The sizing engine penalizes positions where calibration is poor — more money into high-confidence zones, less into extremes.

---

## How It Works

### The Scan Loop

```
1. Find next game (Markov constraint: don't price Game 4 using pre-Game-3 data)
2. Run all 6 models on that matchup → generate predictions
3. For each sub-market (134+ per game):
   - Convert prediction to threshold probability
   - Compare to live orderbook price (via WebSocket)
   - If edge > fee breakeven × buffer → signal
4. Size signals by: edge × confidence × model_accuracy × tail_discount
5. Apply cluster inventory caps (prevent correlated concentration)
6. Quote at top of book (tight, not wide spreads)
7. On game settlement (via WebSocket) → sync data → rebuild features → scan next game
```

### Market Types We Trade

| Kalshi Series | Our Model | What It Predicts | Markets/Game |
|---|---|---|---|
| `KXNBAGAME` | `winner` | P(home wins) — binary | 2 |
| `KXNBASPREAD` | `spread` | Home margin of victory (continuous) | ~44 |
| `KXNBATOTAL` | `total` | Combined points scored (continuous) | ~11 |
| `KXNBA1HSPREAD` | `h1_spread` | First half margin (continuous) | ~15 |
| `KXNBA1HTOTAL` | `h1_total` | First half total points (continuous) | ~9 |
| `KXNBA1HWINNER` | `home_wins_h1` | P(home wins first half) — binary | 3 |

For regression models (spread, total), we predict a point estimate and convert it to binary probabilities using a calibrated t-distribution:

```
P(spread > threshold) = 1 - t.cdf((threshold - predicted) / scale, df)
```

The `df` and `scale` parameters come from the model's out-of-fold residuals — they encode how uncertain the model actually is, not how certain it claims to be.

---

## Diversification Strategy

### The Problem

29 signals from one game LOOK diverse but aren't. If NYK loses, most of them lose together. The effective independence is much less than 29.

### Correlation Clusters

We group signals by what underlying outcome they depend on:

| Cluster | What Drives It | Example | Cap |
|---|---|---|---|
| **direction** | Who wins (binary) | Winner + spread ≤3 | 15 contracts |
| **magnitude** | Margin of victory (conditional on winning) | Spread 4-12 | 10 contracts |
| **total** | Combined scoring (weakly correlated with winner) | Over/under 218 | 10 contracts |
| **h1** | First-half outcomes (partially independent of full game) | H1 spread, H1 total | 10 contracts |

Cluster caps prevent "29 signals that are secretly one bet" from blowing up the account. Each cluster gets its own budget. The best signal per cluster fills first, then the next best, until the cap is hit.

### Why This Works

- NYK can win by 2 (direction pays, magnitude doesn't)
- A game can be high-scoring regardless of who wins (total is independent)
- NYK can lead at halftime but lose the game (h1 partially independent)
- A blowout doesn't mean high total (pace varies)

These are genuinely different dimensions of the same game.

---

## Sizing: Distribution-Aware Kelly

Position size = `kelly_raw × KELLY_FRACTION × confidence_mult × model_accuracy × threshold_discount`

### Kelly Raw
Standard Kelly criterion: `edge / (1 - price)`. This is the theoretical optimal bet fraction for a binary outcome.

### KELLY_FRACTION = 0.25 (Quarter Kelly)
We bet 1/4 of what Kelly says. Full Kelly maximizes long-run growth but has catastrophic drawdowns. Quarter-Kelly sacrifices ~25% of growth for ~75% less variance.

### Confidence Multiplier
From ensemble specialist disagreement (standard deviation of predictions):
- HIGH (std ≤ 1.28): 1.0x — specialists agree, full conviction
- MEDIUM (std ≤ 1.80): 0.75x
- LOW (std > 1.80): 0.5x — specialists disagree, halve the bet

### Model Accuracy Weight
Not all models are equally good:
- `winner`: 1.0 (best-calibrated, 17 specialists)
- `spread`: 0.9 (good, but penalized further per-threshold)
- `h1_spread`: 0.85
- `total`: 0.7 (MAE=14.5 on a 210-point scale, noisier)

### Threshold Discount (The Critical One)

This is where QQ-plot findings directly translate to money. From OOF calibration analysis:

**Spread model:**
- Threshold 1-5: bias < 0.5% → discount = **1.0** (full confidence)
- Threshold 5-8: bias ~1.5% → discount = **0.85**
- Threshold 8-10: bias ~2% → discount = **0.70**
- Threshold 10-13: bias 2-3% → discount = **0.50**
- Threshold 13-16: bias 3-8% → discount = **0.30**
- Threshold 16+: extreme tails, unreliable → discount = **0.15**

This means: a 10% edge at threshold 15 (discount 0.30) gets sized the same as a 3% edge at threshold 3 (discount 1.0). The model's certainty about extreme outcomes is not trustworthy — we price accordingly.

---

## Top-of-Book Quoting

We DON'T post wide bid-ask spreads (like 5c wide around fair value). The markets are thin and the spread is already 1-2c.

Instead: post at the **top of the existing book**, but only if that price is below our fair value.

```python
our_bid = best_bid + 1  # one tick better than current best
if our_bid >= fair_value:
    our_bid = fair_value - 1  # never pay more than fair
```

This means:
- We're always at the front of the queue (priority fill)
- We never overpay (bid capped below fair)
- We exit at top of book when the price is right — not by sweeping deep into the book

---

---

## Markov Constraint: One Game Ahead Only

NBA playoff series are sequential. The outcome of Game 3 changes everything about Game 4 pricing:
- P(NYK wins Game 4 | NYK won Game 3) ≠ P(NYK wins Game 4 | NYK lost Game 3)

Our features (rolling averages, momentum, etc.) will be stale for Game 4 until Game 3 data is synced. The market, however, prices Game 4 immediately using the new information.

**Solution:** Only trade the NEXT game per matchup. After it settles:
1. WebSocket `market_lifecycle_v2` fires `settled` event
2. `sync_games.py` runs (~5 min) to pull box scores
3. `build_features_only` rebuilds the parquet with fresh data
4. Models reload and we're ready to trade the next game with honest features

This is event-driven, not cron-based. No stale data, no adverse selection.

---

## Backtest Results

From historical simulation over all Mar-May 2026 playoff games (Kalshi trade tape, 466 tickers, 11.1M trades):

| Strategy | Sharpe | Total P&L | Win Rate | Trades | Max Drawdown |
|---|---|---|---|---|---|
| **Maker** (exit pre-tipoff) | 13.28 | $515 | 71.4% | 454 | -$12 |
| **Hybrid** (MM + hold aligned) | 9.06 | $677 | 66.3% | 454 | -$29 |
| **Taker** (buy and hold) | 2.99 | $442 | 36.0% | 353 | -$121 |

Maker has the best risk-adjusted return (tiny drawdown). Hybrid makes the most money but takes settlement risk. Taker is simplest but most volatile.

Best hybrid parameters: spread=4c, hold_edge_threshold=0.05, confidence_gate=ALL.

---

## Architecture

```
trading/
├── runner.py       Main loop: find game → scan → size → execute
├── scanner.py      Multi-model signal generation across all market types
├── sizing.py       Distribution-aware Kelly with cluster caps
├── models.py       Load all 6 ensembles, regression→probability conversion
├── ws.py           WebSocket: real-time orderbook + settlement triggers
├── executor.py     Order placement (dry-run / live), logging
├── portfolio.py    JSON position ledger, P&L tracking
├── risk.py         Circuit breaker, exposure limits, timing gates
├── backtest.py     Historical simulation of strategies
├── config.py       All tunable parameters
├── logs/           Daily order logs + WS trade tape (JSONL)
├── state/          positions.json (live ledger)
└── output/         Backtest results, equity curves
```

### Data Flow

```
game_features.parquet ──→ 6 ensemble models ──→ predictions
                                                     │
Kalshi API/WS ─→ orderbook prices ────────────────→ edge computation
                                                     │
                                              signal generation (29 per game)
                                                     │
                                              sizing engine (→ 3 diversified)
                                                     │
                                              execution (top-of-book quote)
```

---

## Usage

```bash
# Dry-run, single scan (safest — verify signals)
conda run -n pred python -m trading.runner --dry-run --once --bankroll 350

# Dry-run, continuous (watch signals over time)
conda run -n pred python -m trading.runner --dry-run --interval 30 --bankroll 350

# Live trading (REAL MONEY)
conda run -n pred python -m trading.runner --live --once --bankroll 350

# WebSocket standalone (watch books + tape)
conda run -n pred python -m trading.ws

# REST-only mode (no WebSocket)
conda run -n pred python -m trading.runner --dry-run --once --no-ws
```

### Flags

| Flag | Default | Effect |
|---|---|---|
| `--dry-run` | on | Log orders, don't place them |
| `--live` | off | Actually place orders (uses write key) |
| `--once` | off | Single scan then exit |
| `--interval N` | 5 | Minutes between scans |
| `--strategy` | hybrid | `taker`, `maker`, or `hybrid` |
| `--bankroll` | 350 | Dollars for Kelly sizing |
| `--no-ws` | off | Disable WebSocket, REST-only |

---

## Fee Model

Kalshi charges per contract, scaling with price uncertainty:

| Role | Fee Formula | At 50c | At 70c |
|---|---|---|---|
| **Taker** (aggress book) | 0.07 × P × (1-P) | 1.75c | 1.47c |
| **Maker** (passive limit) | 0.0175 × P × (1-P) | 0.44c | 0.37c |

Maker fee is 4× cheaper. This is why the maker strategy dominates — it needs far less edge to be profitable.

Minimum edge to break even:
- Taker: ~0.07 × P (at 55c: need 3.8c edge minimum)
- Maker: ~0.0175 × P (at 55c: need 0.96c edge minimum)

We require 1.5× the breakeven edge as a safety buffer.

---

## Risk Controls

1. **Daily loss circuit breaker**: stops all trading if daily P&L < -5% of bankroll
2. **Per-cluster inventory caps**: 10-15 contracts max per correlation cluster
3. **Single position cap**: 5% of bankroll per market
4. **Total exposure cap**: 20% of bankroll across all positions
5. **Timing gates**: no entries within 30min of tipoff, no entries >7 days out
6. **Price filters**: skip prices below 15c or above 85c (extreme odds = extreme variance)
7. **Conviction filter**: skip if model probability < 53% (no edge, just noise)

---

## Live Example (Game 3: SAS @ NYK, June 8 2026)

```
Models predict:
  - NYK wins: 59.2%
  - NYK spread: +4.8 points
  - H1 NYK spread: +2.7 points
  - H1 total: 112.5 points

Market state:
  - 134 sub-markets open
  - Winner: NYK-YES at 55c (model says 59c → 4.2% edge)
  - Spread ladder: 44 thresholds from SAS+1 to NYK+20

Scanner output:
  - 29 signals pass edge threshold

After sizing (tail discount + cluster caps):
  3 positions executed:
    [magnitude]  SAS wins by 6+ NO  × 10  @ 17c  edge=11.8%  discount=0.85
    [direction]  SAS wins by 3+ NO  × 15  @ 24c  edge=11.6%  discount=1.00
    [h1]         H1 SAS wins by 2+ NO × 10 @ 31c  edge=9.2%   discount=1.00

  Total exposure: $7.80 / $350 bankroll = 2.2%
```

The system bet on three related-but-distinct outcomes:
- NYK wins (direction)
- NYK wins comfortably (magnitude)
- NYK leads at halftime (h1 — partially independent dimension)

A close NYK win (say 105-103): direction and h1 might pay, magnitude doesn't. A SAS upset: all lose but exposure was only 2.2%. A NYK blowout: all three pay.

---

## Known Limitations

1. **Single matchup during Finals.** When only SAS vs NYK is playing, there's no cross-game diversification. In the regular season with 5+ games/night, the system would spread across truly independent events.

2. **Playoff calibration.** Model confidence thresholds were trained on regular season data. ALL playoff games classify as LOW confidence (std > 0.038). This is conservative but appropriate — playoffs are harder to predict.

3. **Tail overconfidence.** The spread model predicts P(wins by 15+) about 3-8% too high. The threshold discount corrects for this, but it's a blunt instrument. Better: re-fit the t-distribution tails on recent data.

4. **Arbs at extremes.** The detected arbitrage opportunities (1-12c) are at very thin liquidity levels. Executing them in size may not be feasible — but they're free when fillable.

5. **WebSocket disconnects.** The WS drops after ~10s of inactivity in some conditions. Reconnect logic handles this, but there may be brief windows without real-time data. REST fallback covers the gap.

---

## Credentials

- **Read-only API key**: `KALSHI_API_KEY` in `.env` + RSA key at `backtest.txt`
- **Write-enabled key**: `KALSHI_WRITE_KEY` in `.env` + RSA key at `trade.txt`
- Dry-run mode uses the read-only key. `--live` mode requires the write key.
