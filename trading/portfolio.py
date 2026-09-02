"""
trading/portfolio.py
--------------------
Position ledger backed by the Kalshi API in live mode.

Live mode:
- Initial state from REST (GET /portfolio/positions) at each scan via refresh()
- Real-time updates via wss://external-api-ws.kalshi.com/market_positions
- add_position() writes an optimistic "pending" entry to prevent double-ordering
  before the WS confirms; _refresh_from_api() merges API truth over pending entries
- All position events logged to logs/YYYY-MM-DD_positions.jsonl

Dry-run mode:
- Pure in-memory state, no API reads or writes
- Logged to logs/YYYY-MM-DD_positions_dry.jsonl
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import websocket

logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

POSITIONS_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"

# ── Module state ──────────────────────────────────────────────────────────────

_dry_run: bool = True
_client = None
_pos_ws: Optional[_PositionsWS] = None  # set by init()

# Dry-run: single in-memory dict
_mem: dict = {"positions": [], "open_orders": []}

# Live: indexed by ticker for O(1) has_position; populated by REST + WS
_live_positions: dict[str, dict] = {}
_live_orders: dict[str, dict] = {}  # ticker → resting order info (prevents duplicate posting)
_live_lock = threading.Lock()


# ── WS for real-time position updates ────────────────────────────────────────

class _PositionsWS:
    """
    Subscribes to Kalshi market_positions feed and keeps _live_positions in sync.
    Authentication uses the same RSA-PSS pattern as the orderbook WS.
    """

    def __init__(self, api_key: str, private_key):
        self._api_key = api_key
        self._private_key = private_key
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._msg_id = 0

    def _auth_headers(self) -> dict:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        import base64
        ts_ms = int(time.time() * 1000)
        msg = f"{ts_ms}GET/trade-api/ws/v2".encode("utf-8")  # must match ws.py auth path
        sig = self._private_key.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": str(ts_ms),
        }

    def _on_open(self, ws):
        logger.info("[POSITIONS WS] Connected")
        self._msg_id += 1
        ws.send(json.dumps({
            "id": self._msg_id,
            "cmd": "subscribe",
            "params": {"channels": ["user_positions"]},
        }))

    def _on_message(self, ws, raw):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        msg_type = msg.get("type", "")
        if msg_type in ("market_position_snapshot", "market_position_update"):
            _apply_position_ws_update(msg.get("msg", {}))

    def _on_error(self, ws, error):
        logger.error(f"[POSITIONS WS] Error: {error}")

    def _on_close(self, ws, code, msg_text):
        logger.warning(f"[POSITIONS WS] Closed: {code} {msg_text}")
        if self._running:
            logger.info("[POSITIONS WS] Reconnecting in 5s...")
            time.sleep(5)
            self._connect()

    def _connect(self):
        headers = self._auth_headers()
        self._ws = websocket.WebSocketApp(
            POSITIONS_WS_URL,
            header=[f"{k}: {v}" for k, v in headers.items()],
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws.run_forever(ping_interval=9, ping_timeout=5)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()
        time.sleep(1)

    def stop(self):
        self._running = False
        if self._ws:
            self._ws.close()


def _apply_position_ws_update(data: dict) -> None:
    """Apply a single market_positions WS message to the live cache."""
    ticker = data.get("market_ticker", "")
    if not ticker:
        return

    position = float(data.get("position_fp", data.get("position", 0)))
    with _live_lock:
        if position == 0:
            old = _live_positions.pop(ticker, None)
            if old:
                logger.info(f"[POS] Closed via WS: {ticker}")
                _log_position_event({"event": "closed", **old}, dry=False)
        else:
            side = "yes" if position > 0 else "no"
            contracts = abs(int(position))
            try:
                exposure = float(data.get("position_cost_dollars", data.get("market_exposure_dollars", 0)))
            except (ValueError, TypeError):
                exposure = 0.0
            entry_price = exposure / contracts if contracts else 0.0

            record = {
                "ticker": ticker,
                "side": side,
                "contracts": contracts,
                "entry_price": entry_price,
                "status": "open",
            }
            _live_positions[ticker] = record
            logger.debug(f"[POS] WS update: {contracts}x {side} on {ticker}")
            _log_position_event({"event": "ws_update", **record}, dry=False)


# ── Init / refresh ────────────────────────────────────────────────────────────

def init(client, dry_run: bool) -> None:
    """
    Call once at startup.
    - dry_run=True: all state is in-memory; API is used read-only (market data only).
    - dry_run=False: positions come from Kalshi API + WS; positions.json never written.
    """
    global _dry_run, _client, _pos_ws, _mem, _live_positions

    _dry_run = dry_run
    _client = client

    if dry_run:
        _mem = {"positions": [], "open_orders": []}
        logger.info("[DRY] Portfolio state is in-memory only (no API writes)")
    else:
        _live_positions = {}
        _refresh_from_api()

        # Start real-time WS for position updates
        from backtest.kalshi_client import _load_private_key
        import os
        from pathlib import Path as _Path
        api_key = os.environ.get("KALSHI_API_KEY", "")
        rsa_path = _Path(__file__).resolve().parents[1] / "backtest.txt"
        if api_key and rsa_path.exists():
            _pos_ws = _PositionsWS(api_key, _load_private_key(rsa_path))
            _pos_ws.start()
            logger.info("[LIVE] Portfolio state from Kalshi API + positions WS")
        else:
            logger.warning("[LIVE] Positions WS skipped (no API key or key file). REST only.")


def refresh() -> None:
    """
    Sync live position cache from REST. Call at the start of each scan.
    No-op in dry-run mode.
    """
    if not _dry_run:
        _refresh_from_api()


def _refresh_from_api() -> None:
    global _live_positions, _live_orders
    try:
        resp = _client.get_positions()
        api_positions = resp.get("market_positions", [])
        with _live_lock:
            new_pos: dict[str, dict] = {}
            for p in api_positions:
                ticker = p.get("ticker", p.get("market_ticker", ""))
                position = float(p.get("position_fp", p.get("position", 0)))
                if not ticker or position == 0:
                    continue
                side = "yes" if position > 0 else "no"
                contracts = abs(int(position))
                try:
                    exposure = float(p.get("market_exposure_dollars", p.get("position_cost_dollars", 0)))
                except (ValueError, TypeError):
                    exposure = 0.0
                entry_price = exposure / contracts if contracts else 0.0
                existing = _live_positions.get(ticker, {})
                new_pos[ticker] = {
                    "ticker": ticker,
                    "side": side,
                    "contracts": contracts,
                    "entry_price": entry_price or existing.get("entry_price", 0.0),
                    "status": "open",
                }
            # Keep pending optimistic entries not yet confirmed by API
            for ticker, rec in _live_positions.items():
                if ticker not in new_pos and rec.get("status") == "pending":
                    new_pos[ticker] = rec
            _live_positions = new_pos

        # Sync resting orders from API (source of truth for what's on the book)
        try:
            resp_orders = _client.get_orders(status="resting")
            api_orders = resp_orders.get("orders", [])
            with _live_lock:
                new_orders: dict[str, dict] = {}
                for o in api_orders:
                    ticker = o.get("ticker", "")
                    if not (ticker.startswith("KXNBA") or ticker.startswith("KXWNBA")):
                        continue
                    new_orders[ticker] = {
                        "ticker": ticker,
                        "side": o.get("side", ""),
                        "order_id": o.get("order_id", ""),
                        "contracts": int(float(o.get("remaining_count_fp", o.get("remaining_count", 0)))),
                        "price_cents": round(float(o.get("yes_price_dollars", "0")) * 100)
                                       if o.get("side") == "yes"
                                       else round(float(o.get("no_price_dollars", "0")) * 100),
                    }
                _live_orders = new_orders
        except Exception as e:
            logger.warning(f"[POS] Resting orders refresh failed: {e}")

        logger.info(f"[POS] Refreshed from API: {len(_live_positions)} open positions, "
                    f"{len(_live_orders)} resting orders")
    except Exception as e:
        logger.warning(f"[POS] API refresh failed: {e}")


# ── Logging ───────────────────────────────────────────────────────────────────

def _log_position_event(event: dict, dry: bool) -> None:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suffix = "_dry" if dry else ""
    log_file = LOGS_DIR / f"{date_str}_positions{suffix}.jsonl"
    event["log_time"] = datetime.now(timezone.utc).isoformat()
    with open(log_file, "a") as f:
        f.write(json.dumps(event, default=str) + "\n")


# ── Public interface ──────────────────────────────────────────────────────────

def has_position(ticker: str) -> bool:
    """Check if we have a filled position OR a resting order on this ticker."""
    if _dry_run:
        return (any(p["ticker"] == ticker for p in _mem["positions"]) or
                any(o["ticker"] == ticker for o in _mem["open_orders"]))
    with _live_lock:
        return ticker in _live_positions or ticker in _live_orders


def has_filled_position(ticker: str) -> bool:
    """Check if we have a confirmed filled position (excludes resting orders)."""
    if _dry_run:
        return any(p["ticker"] == ticker for p in _mem["positions"])
    with _live_lock:
        return ticker in _live_positions


def has_open_order(ticker: str) -> bool:
    """Check if we have a resting (unfilled) order on this ticker."""
    if _dry_run:
        return any(o["ticker"] == ticker for o in _mem["open_orders"])
    with _live_lock:
        return ticker in _live_orders


def get_open_order(ticker: str) -> dict | None:
    """Return the resting order record for a ticker, or None."""
    if _dry_run:
        for o in _mem["open_orders"]:
            if o["ticker"] == ticker:
                return o
        return None
    with _live_lock:
        return _live_orders.get(ticker)


def get_positions() -> list[dict]:
    if _dry_run:
        return list(_mem["positions"])
    with _live_lock:
        return list(_live_positions.values())


def add_position(
    ticker: str,
    side: str,
    entry_price: float,
    contracts: int,
    strategy: str,
    order_id: str = "",
) -> None:
    record = {
        "ticker": ticker,
        "side": side,
        "entry_price": entry_price,
        "contracts": contracts,
        "strategy": strategy,
        "order_id": order_id,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "status": "open" if _dry_run else "pending",
    }
    if _dry_run:
        _mem["positions"].append(record)
    else:
        # Optimistic entry — prevents double-ordering until WS/refresh confirms
        with _live_lock:
            if ticker not in _live_positions:
                _live_positions[ticker] = record
    logger.info(f"{'[DRY] ' if _dry_run else '[LIVE] '}Position added: {contracts}x {side} @ {entry_price:.2f} on {ticker}")
    _log_position_event({"event": "add", **record}, dry=_dry_run)


def add_open_order(
    ticker: str,
    side: str,
    price_cents: int,
    contracts: int,
    order_id: str,
    order_type: str = "maker",
    model_prob: float | None = None,
) -> None:
    record = {
        "ticker": ticker,
        "side": side,
        "price_cents": price_cents,
        "contracts": contracts,
        "order_id": order_id,
        "order_type": order_type,
        "placed_at": datetime.now(timezone.utc).isoformat(),
    }
    if model_prob is not None:
        record["model_prob"] = model_prob
    if _dry_run:
        _mem["open_orders"].append(record)
    else:
        with _live_lock:
            _live_orders[ticker] = record
    _log_position_event({"event": "open_order", **record}, dry=_dry_run)


def get_open_orders() -> list[dict]:
    if _dry_run:
        return list(_mem["open_orders"])
    # Live: use the already-populated _live_orders cache (populated by _refresh_from_api)
    # rather than making a redundant REST call.
    with _live_lock:
        return list(_live_orders.values())


def remove_open_order(order_id: str) -> None:
    global _live_orders
    if _dry_run:
        _mem["open_orders"] = [o for o in _mem["open_orders"] if o["order_id"] != order_id]
    else:
        with _live_lock:
            _live_orders = {t: o for t, o in _live_orders.items() if o.get("order_id") != order_id}


def position_count() -> int:
    if _dry_run:
        return len(_mem["positions"])
    with _live_lock:
        return len(_live_positions)


def total_exposure() -> float:
    """Total dollars at risk: filled positions + resting orders (potential fills)."""
    if _dry_run:
        pos_exp = sum(p["entry_price"] * p["contracts"] for p in _mem["positions"])
        ord_exp = sum(o["price_cents"] / 100.0 * o["contracts"] for o in _mem["open_orders"])
        return pos_exp + ord_exp
    with _live_lock:
        pos_exp = sum(p["entry_price"] * p["contracts"] for p in _live_positions.values())
        ord_exp = sum(o["price_cents"] / 100.0 * o["contracts"] for o in _live_orders.values())
        return pos_exp + ord_exp


def daily_pnl() -> float:
    """
    Dry-run: tracks simulated P&L from settle_position calls.
    Live: returns 0 — settlement tracking via WS is not yet implemented;
    the circuit breaker in risk.py is effectively disabled.
    TODO: accumulate realized P&L from market_positions WS close events.
    """
    if _dry_run:
        return _mem.get("daily_pnl", 0.0)
    return 0.0


def summary() -> str:
    n_open = position_count()
    exposure = total_exposure()
    day_pnl = daily_pnl()
    balance_str = ""
    if not _dry_run and _client:
        try:
            bal = _client.get_balance()
            balance_str = f" | Balance: ${bal.get('balance', 0) / 100:.2f}"
        except Exception:
            pass
    return (
        f"Positions: {n_open} open | "
        f"Exposure: ${exposure:.2f} | "
        f"Day P&L: ${day_pnl:.2f}"
        f"{balance_str}"
    )


def stop() -> None:
    """Gracefully stop the positions WS. Call on shutdown."""
    if _pos_ws:
        _pos_ws.stop()
