"""
kalshi_client.py
----------------
Kalshi REST API client using RSA-PSS authentication.

Supports both live trading (PROD) and demo environments.
All timestamps use UTC. Token cached per session.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


# ── Auth ──────────────────────────────────────────────────────────────────────

def _load_private_key(pem_path: str | Path):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    pem_bytes = Path(pem_path).read_bytes()
    return load_pem_private_key(pem_bytes, password=None)


def _sign_request(private_key, method: str, path: str, ts_ms: int) -> str:
    """
    Sign: timestamp_ms + METHOD + /trade-api/v2{path}  (no body, no query params).
    Uses RSA-PSS SHA-256.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    # Strip query string — docs say sign path without query params
    clean_path = path.split("?")[0]
    # Kalshi expects the full path from root e.g. /trade-api/v2/portfolio/balance
    full_path = f"/trade-api/v2{clean_path}"
    msg = f"{ts_ms}{method}{full_path}".encode("utf-8")
    sig = private_key.sign(msg, padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.DIGEST_LENGTH,
    ), hashes.SHA256())
    return base64.b64encode(sig).decode("utf-8")


# ── Client ────────────────────────────────────────────────────────────────────

class KalshiClient:
    """
    Thin wrapper around the Kalshi REST API.

    Args:
        api_key:     KALSHI_API_KEY (from .env)
        rsa_key_path: path to RSA private key PEM
        env:         "prod" or "demo"
    """

    PROD_BASE = "https://api.elections.kalshi.com/trade-api/v2"
    EXTERNAL_BASE = "https://api.elections.kalshi.com/trade-api/v2"
    DEMO_BASE = "https://demo-api.kalshi.co/trade-api/v2"

    def __init__(self, api_key: str, rsa_key_path: str | Path, env: str = "prod"):
        self._api_key = api_key
        self._private_key = _load_private_key(rsa_key_path)
        self._base = self.PROD_BASE if env == "prod" else self.DEMO_BASE
        self._token: str | None = None

    # ── Low-level ─────────────────────────────────────────────────────────────

    def _headers(self, method: str, path: str) -> dict:
        ts_ms = int(time.time() * 1000)
        sig = _sign_request(self._private_key, method.upper(), path, ts_ms)
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": str(ts_ms),
        }

    def _request(self, method: str, path: str, params: dict | None = None,
                 body: dict | None = None) -> Any:
        url = self._base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        body_str = json.dumps(body) if body else ""
        # Sign path without query string (docs requirement)
        headers = self._headers(method, path)

        data = body_str.encode() if body_str else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode()
            raise RuntimeError(f"Kalshi API {e.code}: {body_txt}") from e

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict | None = None) -> Any:
        return self._request("POST", path, body=body)

    # ── Market endpoints ──────────────────────────────────────────────────────

    def get_markets(self, **kwargs) -> dict:
        """List markets. Pass status="open", series_ticker="KXNBA", etc."""
        return self.get("/markets", params=kwargs)

    def get_market(self, ticker: str) -> dict:
        return self.get(f"/markets/{ticker}")

    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        return self.get(f"/markets/{ticker}/orderbook", params={"depth": depth})

    def get_trades(self, ticker: str | None = None, **kwargs) -> dict:
        """Get trade tape. Pass ticker= to filter by market."""
        params = dict(kwargs)
        if ticker:
            params["ticker"] = ticker
        return self.get("/markets/trades", params=params)

    def get_candlesticks(self, series_ticker: str, ticker: str,
                         start_ts: int, end_ts: int,
                         period_interval: int = 60) -> dict:
        """OHLC candles. period_interval: 1, 60, or 1440 minutes."""
        return self.get(
            f"/series/{series_ticker}/markets/{ticker}/candlesticks",
            params={"start_ts": start_ts, "end_ts": end_ts,
                    "period_interval": period_interval},
        )

    def get_historical_candlesticks(self, ticker: str,
                                     start_ts: int, end_ts: int,
                                     period_interval: int = 60) -> dict:
        """OHLC candles for settled/archived markets."""
        return self.get(
            f"/historical/markets/{ticker}/candlesticks",
            params={"start_ts": start_ts, "end_ts": end_ts,
                    "period_interval": period_interval},
        )

    def get_historical_trades(self, ticker: str | None = None,
                               min_ts: int | None = None,
                               max_ts: int | None = None,
                               limit: int = 1000) -> dict:
        """Trades from archived/settled markets."""
        params: dict = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        return self.get("/historical/trades", params=params)

    def get_series(self, series_ticker: str) -> dict:
        return self.get(f"/series/{series_ticker}")

    def get_events(self, **kwargs) -> dict:
        return self.get("/events", params=kwargs)

    def get_event(self, event_ticker: str) -> dict:
        return self.get(f"/events/{event_ticker}")

    # ── Portfolio endpoints ───────────────────────────────────────────────────

    def get_balance(self) -> dict:
        return self.get("/portfolio/balance")

    def get_positions(self, **kwargs) -> dict:
        return self.get("/portfolio/positions", params=kwargs)

    def get_fills(self, **kwargs) -> dict:
        return self.get("/portfolio/fills", params=kwargs)

    # ── Order endpoints ───────────────────────────────────────────────────────

    def create_order(self, ticker: str, side: str, action: str,
                     count: int, price: int, order_type: str = "limit",
                     client_order_id: str | None = None) -> dict:
        """
        Place a limit order.

        Args:
            ticker:    market ticker (e.g. "KXNBA-25MAY01-T210.5")
            side:      "yes" or "no"
            action:    "buy" or "sell"
            count:     number of contracts
            price:     cents (1–99)
            order_type: "limit" or "market"
        """
        # API requires exactly one of yes_price/no_price; yes_price is canonical
        yes_price = price if side == "yes" else 100 - price
        body = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
            "yes_price": yes_price,
        }
        if client_order_id:
            body["client_order_id"] = client_order_id
        return self.post("/portfolio/orders", body=body)

    def cancel_order(self, order_id: str) -> dict:
        return self._request("DELETE", f"/portfolio/orders/{order_id}")

    def get_orders(self, **kwargs) -> dict:
        return self.get("/portfolio/orders", params=kwargs)


# ── Factory ───────────────────────────────────────────────────────────────────

def make_client(env: str = "prod") -> KalshiClient:
    """Build client from environment variables + backtest.txt RSA key (read-only)."""
    api_key = os.environ.get("KALSHI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("KALSHI_API_KEY not set")

    project_root = Path(__file__).resolve().parents[1]
    rsa_path = project_root / "backtest.txt"
    if not rsa_path.exists():
        raise FileNotFoundError(f"RSA key not found at {rsa_path}")

    return KalshiClient(api_key=api_key, rsa_key_path=rsa_path, env=env)


def make_write_client(env: str = "prod") -> KalshiClient:
    """Build client with write permissions for order placement."""
    api_key = os.environ.get("KALSHI_WRITE_KEY", "")
    if not api_key:
        raise EnvironmentError("KALSHI_WRITE_KEY not set")

    project_root = Path(__file__).resolve().parents[1]
    rsa_path = project_root / "trade.txt"
    if not rsa_path.exists():
        raise FileNotFoundError(f"RSA write key not found at {rsa_path}")

    return KalshiClient(api_key=api_key, rsa_key_path=rsa_path, env=env)
