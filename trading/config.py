"""
trading/config.py
-----------------
All trading parameters. Values will be tuned after backtest Phase 1.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADING_DIR = Path(__file__).resolve().parent
LOGS_DIR = TRADING_DIR / "logs"
STATE_DIR = TRADING_DIR / "state"

# ── Strategy selection ───────────────────────────────────────────────────────
STRATEGY = "hybrid"  # "taker" | "maker" | "hybrid"

# ── Execution mode ───────────────────────────────────────────────────────────
DRY_RUN = True

# ── Position sizing ──────────────────────────────────────────────────────────
KELLY_FRACTION = 0.25
MAX_POSITION_PCT = 5.0          # max single position as % of bankroll
MAX_DAILY_EXPOSURE_PCT = 40.0   # max total capital at risk (raised: most resting orders won't fill)
MAX_CONCURRENT_POSITIONS = 30   # raised: spread ladder posts many resting orders
MAX_CONTRACTS_PER_MARKET = 20

# ── Edge thresholds ──────────────────────────────────────────────────────────
MIN_EDGE_BUFFER_TAKER = 1.5     # edge must exceed taker_breakeven * this
MIN_EDGE_BUFFER_MAKER = 1.5     # edge must exceed maker_breakeven * this
MIN_MODEL_CONVICTION = 0.53     # skip if model_prob < this (model is "terrible")

# ── Tiered execution ────────────────────────────────────────────────────────
# Signals with edge above taker threshold get taken immediately (guaranteed fill).
# Signals between maker and taker thresholds get posted as resting limit orders.
TAKER_EDGE_THRESHOLD = 1.5     # edge >= taker_breakeven * this → take immediately
CANCEL_BEFORE_TIPOFF_MIN = 10  # cancel unfilled resting orders this many min before tipoff
REPRICE_MIN_TICK_MOVE = 1      # only reprice if target price differs by at least this many cents

# ── Risk limits ──────────────────────────────────────────────────────────────
DAILY_LOSS_LIMIT_PCT = 5.0      # circuit breaker

# ── Timing ───────────────────────────────────────────────────────────────────
MIN_HOURS_TO_TIPOFF = 1.0       # no trading within 1h of tipoff
MAX_HOURS_TO_TIPOFF = 168.0     # only active markets
EXIT_BUFFER_MINUTES = 30        # stop maker activity before tipoff

# ── Price filters ────────────────────────────────────────────────────────────
PRICE_FLOOR = 0.15              # avoid extreme longshots
PRICE_CEILING = 0.85            # avoid extreme favorites

# ── Scanning ─────────────────────────────────────────────────────────────────
SCAN_INTERVAL_MINUTES = 5
