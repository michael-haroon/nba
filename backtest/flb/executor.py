"""
executor.py — Future order execution module (NOT IMPLEMENTED).

TODO:
- Read signal JSONs from backtest/output/flb/signals/
- Validate signal is still live: re-fetch market, confirm price hasn't drifted >3¢
- Construct order payload: ticker, side, count, price
- Dry-run mode (default): log the would-be order, do NOT call create_order
- Live mode (--live flag): actually place the order via kalshi_client.create_order
- Maintain positions.json ledger: {ticker, side, entry_price, timestamp, status}
- On settlement: mark P&L in ledger, log result
- Position sizing: based on edge magnitude and Kelly criterion
- Max exposure limits: max concurrent positions, max $ at risk
"""
