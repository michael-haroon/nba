"""
Test Kalshi offset behavior on demo environment.

Goal: Verify that buying NO when you hold YES auto-offsets (nets position to 0).
Steps:
1. Find an open NBA market with liquidity
2. Buy 1x YES (market order at best ask)
3. Check positions → expect +1 YES
4. Buy 1x NO (market order at best ask)
5. Check positions → expect 0 (offset complete)
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.kalshi_client import KalshiClient


def make_demo_client() -> KalshiClient:
    api_key = os.environ.get("KALSHI_DEMO_KEY", "")
    if not api_key:
        raise EnvironmentError("KALSHI_DEMO_KEY not set in .env")
    project_root = Path(__file__).resolve().parents[1]
    rsa_path = project_root / "DEMO.txt"
    if not rsa_path.exists():
        raise FileNotFoundError(f"Demo RSA key not found at {rsa_path}")
    return KalshiClient(api_key=api_key, rsa_key_path=rsa_path, env="demo")


def find_liquid_market(client) -> dict | None:
    """Find an open market with both YES and NO asks available."""
    # Try specific known tickers first
    known_tickers = [
        "KXNBAGAME-26JUN13NYKSAS-SAS",
        "KXNBAGAME-26JUN13NYKSAS-NYK",
    ]
    for ticker in known_tickers:
        try:
            book = client.get_orderbook(ticker, depth=3)
            yes_asks = book.get("orderbook", {}).get("yes", [])
            no_asks = book.get("orderbook", {}).get("no", [])
            print(f"  Checking {ticker}: yes_asks={yes_asks[:2]}, no_asks={no_asks[:2]}")
            if yes_asks and no_asks:
                yes_best_ask = yes_asks[0][0]
                no_best_ask = no_asks[0][0]
                return {"ticker": ticker, "yes_ask": yes_best_ask, "no_ask": no_best_ask}
        except Exception as e:
            print(f"  {ticker}: {e}")

    # Broader search across all NBA series
    for series in ["KXNBAGAME", "KXNBATOTAL", "KXNBASPREAD"]:
        try:
            result = client.get_markets(series_ticker=series, status="open", limit=50)
            markets = result.get("markets", [])
            print(f"  Series {series}: {len(markets)} markets")
            for m in markets:
                ticker = m.get("ticker", "")
                if not ticker:
                    continue
                try:
                    book = client.get_orderbook(ticker, depth=3)
                    yes_asks = book.get("orderbook", {}).get("yes", [])
                    no_asks = book.get("orderbook", {}).get("no", [])
                    if yes_asks and no_asks:
                        yes_best_ask = yes_asks[0][0]
                        no_best_ask = no_asks[0][0]
                        if 15 <= yes_best_ask <= 85:
                            return {"ticker": ticker, "yes_ask": yes_best_ask, "no_ask": no_best_ask}
                except Exception:
                    continue
        except Exception as e:
            print(f"  Series {series} failed: {e}")

    # Last resort: any open market
    try:
        result = client.get_markets(status="open", limit=200)
        all_markets = result.get("markets", [])
        print(f"  All open markets: {len(all_markets)}")
        for m in all_markets[:50]:
            ticker = m.get("ticker", "")
            if not ticker:
                continue
            try:
                book = client.get_orderbook(ticker, depth=3)
                yes_asks = book.get("orderbook", {}).get("yes", [])
                no_asks = book.get("orderbook", {}).get("no", [])
                if yes_asks and no_asks:
                    yes_best_ask = yes_asks[0][0]
                    no_best_ask = no_asks[0][0]
                    if 15 <= yes_best_ask <= 85:
                        return {"ticker": ticker, "yes_ask": yes_best_ask, "no_ask": no_best_ask}
            except Exception:
                continue
    except Exception as e:
        print(f"  All markets search failed: {e}")

    return None


def get_position_for_ticker(client, ticker: str) -> dict | None:
    """Get current position on a specific ticker."""
    resp = client.get_positions()
    positions = resp.get("market_positions", [])
    for p in positions:
        t = p.get("ticker", p.get("market_ticker", ""))
        if t == ticker:
            return p
    return None


def main():
    print("=" * 60)
    print("KALSHI OFFSET BEHAVIOR TEST (DEMO)")
    print("=" * 60)

    client = make_demo_client()

    # Verify connection
    try:
        bal = client.get_balance()
        print(f"\nConnected. Demo balance: ${bal.get('balance', 0)/100:.2f}")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # Check initial positions
    print("\n--- Step 0: Check initial positions ---")
    resp = client.get_positions()
    positions = resp.get("market_positions", [])
    print(f"Current positions: {len(positions)}")
    for p in positions:
        print(f"  {p.get('ticker')}: position={p.get('position', p.get('position_fp'))}")

    # Find a market
    print("\n--- Step 1: Find a liquid market ---")
    market = find_liquid_market(client)

    if not market:
        print("ERROR: No liquid market found on demo. Cannot test.")
        print("Try checking if the demo environment has active markets.")
        sys.exit(1)

    ticker = market["ticker"]
    yes_ask = market["yes_ask"]
    no_ask = market["no_ask"]
    print(f"Found: {ticker}")
    print(f"  YES best ask: {yes_ask}c")
    print(f"  NO best ask: {no_ask}c")
    print(f"  Total cost (both sides): {yes_ask + no_ask}c")
    print(f"  If both fill: {'PROFIT' if yes_ask + no_ask < 100 else 'LOSS'} of {100 - yes_ask - no_ask}c")

    # Step 2: Buy YES
    print(f"\n--- Step 2: Buy 1x YES @ {yes_ask}c ---")
    try:
        result = client.create_order(
            ticker=ticker,
            side="yes",
            action="buy",
            count=1,
            price=yes_ask,
            order_type="limit",
            client_order_id=f"test_yes_{int(time.time())}",
        )
        print(f"Order result: {result}")
    except Exception as e:
        print(f"Buy YES failed: {e}")
        sys.exit(1)

    time.sleep(1)

    # Step 3: Check position after YES buy
    print("\n--- Step 3: Check position after YES buy ---")
    pos = get_position_for_ticker(client, ticker)
    if pos:
        position_val = pos.get("position_fp", pos.get("position", 0))
        print(f"Position: {position_val} (expected: +1)")
        print(f"Full record: {pos}")
    else:
        print("No position found. Order may not have filled (book moved). Checking orders...")
        orders = client.get_orders(status="resting")
        print(f"Resting orders: {orders.get('orders', [])}")
        print("\nOrder didn't fill. The ask may have moved. Retrying with a higher price or stopping.")
        sys.exit(1)

    # Step 4: Buy NO
    print(f"\n--- Step 4: Buy 1x NO @ {no_ask}c ---")
    try:
        result = client.create_order(
            ticker=ticker,
            side="no",
            action="buy",
            count=1,
            price=no_ask,
            order_type="limit",
            client_order_id=f"test_no_{int(time.time())}",
        )
        print(f"Order result: {result}")
    except Exception as e:
        print(f"Buy NO failed: {e}")
        print("This might indicate that Kalshi doesn't allow buying NO when holding YES?")
        sys.exit(1)

    time.sleep(1)

    # Step 5: Check position after NO buy (expect offset)
    print("\n--- Step 5: Check position after NO buy ---")
    pos = get_position_for_ticker(client, ticker)
    if pos:
        position_val = pos.get("position_fp", pos.get("position", 0))
        print(f"Position: {position_val}")
        if float(position_val) == 0:
            print("RESULT: Position netted to 0. OFFSET CONFIRMED!")
        else:
            print(f"RESULT: Position is {position_val}, NOT netted. Both sides held independently.")
        print(f"Full record: {pos}")
    else:
        print("No position record found for this ticker.")
        print("RESULT: Position disappeared entirely. Likely offset (position=0 → removed from list).")

    # Also check fills to see what happened
    print("\n--- Step 6: Check fills for evidence ---")
    try:
        fills = client.get_fills(ticker=ticker, limit=5)
        for f in fills.get("fills", []):
            print(f"  Fill: {f.get('side')} {f.get('action')} x{f.get('count')} @ {f.get('yes_price')}c")
    except Exception as e:
        print(f"Fills check failed: {e}")

    # Final balance
    print("\n--- Final balance ---")
    bal = client.get_balance()
    print(f"Balance: ${bal.get('balance', 0)/100:.2f}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
