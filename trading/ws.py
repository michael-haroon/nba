"""
trading/ws.py
-------------
Kalshi WebSocket client. Maintains real-time orderbook, trade tape,
and market lifecycle events. Triggers data sync on game settlement.

Usage:
    # Standalone (just listens and logs):
    conda run -n pred python -m trading.ws

    # Programmatic (imported by runner):
    from trading.ws import KalshiWS
    ws = KalshiWS(api_key, rsa_key_path)
    ws.subscribe_market("KXNBAGAME-26JUN08SASNYK-NYK")
    ws.start()  # background thread
    book = ws.get_book("KXNBAGAME-26JUN08SASNYK-NYK")
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import websocket

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest.kalshi_client import _load_private_key, _sign_request

logger = logging.getLogger(__name__)

PROD_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
DEMO_WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class LocalBook:
    """Thread-safe local orderbook maintained from WS snapshots + deltas."""

    def __init__(self):
        self._lock = threading.Lock()
        # {ticker: {"yes": {price_str: size_str}, "no": {price_str: size_str}}}
        self._books: dict[str, dict[str, dict[str, float]]] = {}
        self._seqs: dict[str, int] = {}

    def apply_snapshot(self, ticker: str, yes_levels: list, no_levels: list, seq: int, sid: int):
        with self._lock:
            self._books[ticker] = {
                "yes": {p: float(s) for p, s in (yes_levels or [])},
                "no": {p: float(s) for p, s in (no_levels or [])},
            }
            self._seqs[sid] = seq

    def apply_delta(self, ticker: str, side: str, price: str, delta: float, seq: int, sid: int) -> bool:
        with self._lock:
            last_seq = self._seqs.get(sid, 0)
            if seq <= last_seq:
                return True  # duplicate, ignore

            if seq != last_seq + 1:
                logger.warning(f"Seq gap on {ticker} (sid={sid}): expected {last_seq+1}, got {seq}")
                return False

            self._seqs[sid] = seq
            book = self._books.get(ticker)
            if not book:
                return False

            levels = book[side]
            current = levels.get(price, 0.0)
            new_val = current + delta
            if new_val <= 0:
                levels.pop(price, None)
            else:
                levels[price] = new_val
            return True

    def get_top(self, ticker: str) -> tuple[Optional[int], Optional[int]]:
        """Returns (best_yes_bid_cents, best_yes_ask_cents) or (None, None)."""
        with self._lock:
            book = self._books.get(ticker)
            if not book:
                return None, None

            # Best YES bid = highest price someone will buy YES
            yes_prices = [float(p) for p in book["yes"].keys() if book["yes"][p] > 0]
            # Best YES ask = 100 - highest NO bid price
            no_prices = [float(p) for p in book["no"].keys() if book["no"][p] > 0]

            best_bid = round(max(yes_prices) * 100) if yes_prices else None
            best_ask = 100 - round(max(no_prices) * 100) if no_prices else None

            if best_bid is not None and best_ask is not None and best_bid >= best_ask:
                return None, None
            return best_bid, best_ask

    def get_full(self, ticker: str) -> dict | None:
        """Full book snapshot for a ticker."""
        with self._lock:
            return self._books.get(ticker)

    def has_ticker(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._books


class KalshiWS:
    """
    Persistent WebSocket connection to Kalshi.

    Subscribes to:
    - orderbook_delta (per-market, real-time book)
    - trade (per-market, live tape)
    - market_lifecycle_v2 (global, triggers on settlement)
    """

    def __init__(
        self,
        api_key: str,
        rsa_key_path: str | Path,
        env: str = "prod",
        on_settle: Optional[Callable[[str], None]] = None,
    ):
        self._api_key = api_key
        self._private_key = _load_private_key(rsa_key_path)
        self._url = PROD_WS_URL if env == "prod" else DEMO_WS_URL
        self._on_settle = on_settle

        self.book = LocalBook()
        self._trades: list[dict] = []
        self._trades_lock = threading.Lock()

        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._msg_id = 0
        self._subscribed_tickers: set[str] = set()
        self._pending_resubscribe: set[str] = set()

        # Trade tape log
        self._tape_file = LOGS_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_ws_trades.jsonl"

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _auth_headers(self) -> dict:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        import base64

        ts_ms = int(time.time() * 1000)
        # WS auth signs: {ts_ms}GET/trade-api/ws/v2
        msg = f"{ts_ms}GET/trade-api/ws/v2".encode("utf-8")
        sig = self._private_key.sign(msg, padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ), hashes.SHA256())
        sig_b64 = base64.b64encode(sig).decode("utf-8")
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-SIGNATURE": sig_b64,
            "KALSHI-ACCESS-TIMESTAMP": str(ts_ms),
        }

    def subscribe_market(self, ticker: str):
        """Subscribe to orderbook_delta and trade channels for a market."""
        self._subscribed_tickers.add(ticker)
        if self._ws and self._running:
            self._send_subscribe(ticker)

    def unsubscribe_market(self, ticker: str):
        """Unsubscribe from a market's feeds."""
        self._subscribed_tickers.discard(ticker)
        if self._ws and self._running:
            self._ws.send(json.dumps({
                "id": self._next_id(),
                "cmd": "unsubscribe",
                "params": {"channels": ["orderbook_delta", "trade"], "market_ticker": ticker},
            }))

    def _send_subscribe(self, ticker: str):
        # Orderbook delta
        self._ws.send(json.dumps({
            "id": self._next_id(),
            "cmd": "subscribe",
            "params": {"channels": ["orderbook_delta"], "market_ticker": ticker},
        }))
        # Trade tape
        self._ws.send(json.dumps({
            "id": self._next_id(),
            "cmd": "subscribe",
            "params": {"channels": ["trade"], "market_ticker": ticker},
        }))

    def _send_lifecycle_subscribe(self):
        self._ws.send(json.dumps({
            "id": self._next_id(),
            "cmd": "subscribe",
            "params": {"channels": ["market_lifecycle_v2"]},
        }))

    # ── WebSocket callbacks ──────────────────────────────────────────────────

    def _on_open(self, ws):
        logger.info("WebSocket connected")
        # Subscribe to lifecycle (global)
        self._send_lifecycle_subscribe()
        # Subscribe to all tracked markets
        for ticker in self._subscribed_tickers:
            self._send_subscribe(ticker)

    def _on_message(self, ws, raw):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type", "")

        if msg_type == "subscribed":
            logger.debug(f"Subscribed: {msg.get('msg', {}).get('channel')}")
            return

        if msg_type == "error":
            err = msg.get("msg", {})
            logger.error(f"WS error code={err.get('code')}: {err.get('msg')}")
            return

        if msg_type == "orderbook_snapshot":
            self._handle_snapshot(msg)
        elif msg_type == "orderbook_delta":
            self._handle_delta(msg)
        elif msg_type == "trade":
            self._handle_trade(msg)
        elif msg_type == "market_lifecycle_v2":
            self._handle_lifecycle(msg)

    def _on_error(self, ws, error):
        logger.error(f"WS error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WS closed: {close_status_code} {close_msg}")
        if self._running:
            logger.info("Reconnecting in 5s...")
            time.sleep(5)
            self._connect()

    # ── Message handlers ─────────────────────────────────────────────────────

    def _handle_snapshot(self, msg):
        data = msg.get("msg", {})
        ticker = data.get("market_ticker", "")
        seq = msg.get("seq", 0)
        sid = msg.get("sid", 0)
        yes_levels = data.get("yes_dollars_fp", [])
        no_levels = data.get("no_dollars_fp", [])
        self.book.apply_snapshot(ticker, yes_levels, no_levels, seq, sid)
        bb, ba = self.book.get_top(ticker)
        logger.info(f"[BOOK] Snapshot {ticker}: bid={bb} ask={ba} "
                    f"({len(yes_levels)} yes levels, {len(no_levels)} no levels)")

    def _handle_delta(self, msg):
        data = msg.get("msg", {})
        ticker = data.get("market_ticker", "")
        seq = msg.get("seq", 0)
        sid = msg.get("sid", 0)
        side = data.get("side", "")
        price = data.get("price_dollars", "0")
        delta = float(data.get("delta_fp", "0"))

        ok = self.book.apply_delta(ticker, side, price, delta, seq, sid)
        if not ok:
            # Seq gap — request fresh snapshot by resubscribing
            if ticker not in self._pending_resubscribe:
                self._pending_resubscribe.add(ticker)
                logger.warning(f"[BOOK] Seq gap on {ticker}, resubscribing...")
                self._ws.send(json.dumps({
                    "id": self._next_id(),
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["orderbook_delta"],
                        "market_ticker": ticker,
                        "update_subscription": {"action": "get_snapshot"},
                    },
                }))
                self._pending_resubscribe.discard(ticker)

    def _handle_trade(self, msg):
        data = msg.get("msg", {})
        trade = {
            "ticker": data.get("market_ticker", ""),
            "trade_id": data.get("trade_id", ""),
            "yes_price": data.get("yes_price_dollars", ""),
            "no_price": data.get("no_price_dollars", ""),
            "count": data.get("count_fp", ""),
            "taker_outcome_side": data.get("taker_outcome_side", ""),
            "taker_book_side": data.get("taker_book_side", ""),
            "ts_ms": data.get("ts_ms", 0),
        }

        with self._trades_lock:
            self._trades.append(trade)

        # Log to file
        with open(self._tape_file, "a") as f:
            f.write(json.dumps(trade) + "\n")

    def _handle_lifecycle(self, msg):
        data = msg.get("msg", {})
        event_type = data.get("event_type", "")
        ticker = data.get("market_ticker", "")

        if not ticker.startswith("KXNBAGAME"):
            return

        logger.info(f"[LIFECYCLE] {event_type} → {ticker}")

        if event_type == "settled":
            logger.info(f"[SETTLED] {ticker} — triggering sync pipeline")
            if self._on_settle:
                # Run in separate thread to not block WS
                threading.Thread(
                    target=self._on_settle, args=(ticker,), daemon=True
                ).start()

    # ── Connection management ────────────────────────────────────────────────

    def _connect(self):
        headers = self._auth_headers()
        header_list = [f"{k}: {v}" for k, v in headers.items()]

        self._ws = websocket.WebSocketApp(
            self._url,
            header=header_list,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws.run_forever(ping_interval=9, ping_timeout=5)

    def start(self):
        """Start WS connection in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()
        # Wait for connection
        time.sleep(2)

    def stop(self):
        """Gracefully close."""
        self._running = False
        if self._ws:
            self._ws.close()
        if self._thread:
            self._thread.join(timeout=5)

    def get_recent_trades(self, ticker: str, last_n: int = 50) -> list[dict]:
        """Get recent trades for a ticker from the live tape."""
        with self._trades_lock:
            return [t for t in self._trades[-500:] if t["ticker"] == ticker][-last_n:]

    # ── Convenience ──────────────────────────────────────────────────────────

    def get_book(self, ticker: str) -> tuple[Optional[int], Optional[int]]:
        """Get current best bid/ask in cents. Falls back to None if no data."""
        return self.book.get_top(ticker)


def default_on_settle(ticker: str):
    """Default settlement handler: sync games, rebuild features."""
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    logger.info(f"[SYNC] Running sync_games.py after settlement of {ticker}...")

    sync_ok = False
    for attempt in range(1, 6):
        try:
            result = subprocess.run(
                [sys.executable, "-m",
                 "data_curation.scripts.sync_games", "--workers", "2"],
                capture_output=True, text=True, timeout=600,
                cwd=str(PROJECT_ROOT),
            )
            if result.returncode == 0:
                logger.info("[SYNC] sync_games completed successfully (attempt %d)", attempt)
                sync_ok = True
                break
            else:
                logger.warning("[SYNC] sync_games attempt %d failed (rc=%d): %s",
                               attempt, result.returncode, result.stderr[-300:])
        except subprocess.TimeoutExpired:
            logger.warning("[SYNC] sync_games attempt %d timed out (10min)", attempt)
        if attempt < 5:
            time.sleep(2 ** attempt)

    if not sync_ok:
        logger.error("[SYNC] sync_games failed after 5 attempts — giving up")


def make_ws(env: str = "prod", on_settle: Optional[Callable] = None) -> KalshiWS:
    """Factory using environment variables."""
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("KALSHI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("KALSHI_API_KEY not set")

    project_root = Path(__file__).resolve().parents[1]
    rsa_path = project_root / "backtest.txt"

    return KalshiWS(
        api_key=api_key,
        rsa_key_path=rsa_path,
        env=env,
        on_settle=on_settle or default_on_settle,
    )


def main():
    """Standalone mode: connect, subscribe to all open NBA markets, log."""
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "ws.log"),
        ],
    )

    from backtest.kalshi_client import make_client
    client = make_client("prod")

    # Find open NBA game markets
    result = client.get_markets(series_ticker="KXNBAGAME", status="open", limit=200)
    markets = result.get("markets", [])
    tickers = [m["ticker"] for m in markets]

    logger.info(f"Subscribing to {len(tickers)} markets: {tickers}")

    ws = make_ws("prod")
    for t in tickers:
        ws.subscribe_market(t)

    ws.start()

    try:
        while True:
            time.sleep(10)
            for t in tickers:
                bb, ba = ws.get_book(t)
                if bb is not None:
                    logger.info(f"  {t}: {bb}×{ba}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        ws.stop()


if __name__ == "__main__":
    main()
