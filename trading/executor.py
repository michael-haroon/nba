"""
trading/executor.py
-------------------
Order execution layer. Supports dry-run and live modes.
All orders are logged to trading/logs/ regardless of mode.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _log_order(order: dict, mode: str) -> None:
    """Append order to daily log file. Dry-run writes to a separate _dry file."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    suffix = "_dry" if mode == "dry_run" else ""
    log_file = LOGS_DIR / f"{date_str}_orders{suffix}.jsonl"
    order["log_mode"] = mode
    order["log_time"] = datetime.now(timezone.utc).isoformat()
    with open(log_file, "a") as f:
        f.write(json.dumps(order) + "\n")


def execute_taker(
    client,
    ticker: str,
    side: str,
    contracts: int,
    price_cents: int,
    dry_run: bool = True,
    reason: str = "",
) -> dict | None:
    """
    Place a limit order at the current best ask (taker = immediate fill).

    Args:
        side: "yes" or "no"
        price_cents: the price we're willing to pay (in cents, 1-99)
    """
    order_info = {
        "type": "taker",
        "ticker": ticker,
        "side": side,
        "action": "buy",
        "contracts": contracts,
        "price_cents": price_cents,
        "reason": reason,
        "client_order_id": f"taker_{uuid.uuid4().hex[:12]}",
    }

    if dry_run:
        order_info["status"] = "DRY_RUN"
        logger.info(f"[DRY] BUY {contracts}x {side.upper()} @ {price_cents}c on {ticker}")
        _log_order(order_info, "dry_run")
        return order_info

    for attempt in range(4):
        try:
            time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, 2s, 4s
            result = client.create_order(
                ticker=ticker,
                side=side,
                action="buy",
                count=contracts,
                price=price_cents,
                order_type="limit",
                client_order_id=order_info["client_order_id"],
            )
            order_info["status"] = "SUBMITTED"
            order_info["api_response"] = result
            logger.info(f"[LIVE] BUY {contracts}x {side.upper()} @ {price_cents}c on {ticker} → {result}")
            _log_order(order_info, "live")
            return order_info
        except Exception as e:
            if "429" in str(e) and attempt < 3:
                logger.warning(f"[LIVE] 429 on {ticker}, retrying (attempt {attempt+1})...")
                continue
            order_info["status"] = "ERROR"
            order_info["error"] = str(e)
            logger.error(f"[LIVE] Order FAILED: {e}")
            _log_order(order_info, "live_error")
            return order_info


def execute_maker(
    client,
    ticker: str,
    bid_side: str,
    bid_price_cents: int,
    ask_side: str,
    ask_price_cents: int,
    contracts: int,
    dry_run: bool = True,
    reason: str = "",
) -> dict | None:
    """
    Post passive limit orders on both sides (maker).
    bid_side/ask_side: "yes" or "no"
    """
    order_info = {
        "type": "maker",
        "ticker": ticker,
        "bid_side": bid_side,
        "bid_price_cents": bid_price_cents,
        "ask_side": ask_side,
        "ask_price_cents": ask_price_cents,
        "contracts": contracts,
        "reason": reason,
    }

    if dry_run:
        order_info["status"] = "DRY_RUN"
        logger.info(
            f"[DRY] MAKER {ticker}: "
            f"BID {contracts}x {bid_side.upper()} @ {bid_price_cents}c / "
            f"ASK {contracts}x {ask_side.upper()} @ {ask_price_cents}c"
        )
        _log_order(order_info, "dry_run")
        return order_info

    results = {}
    # Post bid (buy YES below fair)
    bid_id = f"maker_bid_{uuid.uuid4().hex[:12]}"
    try:
        bid_result = client.create_order(
            ticker=ticker,
            side=bid_side,
            action="buy",
            count=contracts,
            price=bid_price_cents,
            order_type="limit",
            client_order_id=bid_id,
        )
        results["bid"] = {"status": "SUBMITTED", "response": bid_result, "order_id": bid_id}
    except Exception as e:
        results["bid"] = {"status": "ERROR", "error": str(e)}
        logger.error(f"[LIVE] Bid order FAILED: {e}")

    # Post ask (sell YES above fair, or equivalently buy NO)
    ask_id = f"maker_ask_{uuid.uuid4().hex[:12]}"
    try:
        ask_result = client.create_order(
            ticker=ticker,
            side=ask_side,
            action="buy",
            count=contracts,
            price=ask_price_cents,
            order_type="limit",
            client_order_id=ask_id,
        )
        results["ask"] = {"status": "SUBMITTED", "response": ask_result, "order_id": ask_id}
    except Exception as e:
        results["ask"] = {"status": "ERROR", "error": str(e)}
        logger.error(f"[LIVE] Ask order FAILED: {e}")

    order_info["results"] = results
    order_info["status"] = "SUBMITTED" if any(
        r.get("status") == "SUBMITTED" for r in results.values()
    ) else "ERROR"
    logger.info(f"[LIVE] MAKER {ticker}: bid={results.get('bid', {}).get('status')}, "
                f"ask={results.get('ask', {}).get('status')}")
    _log_order(order_info, "live")
    return order_info


def cancel_order(client, order_id: str, dry_run: bool = True) -> bool:
    """Cancel an open order."""
    if dry_run:
        logger.info(f"[DRY] CANCEL {order_id}")
        return True
    try:
        client.cancel_order(order_id)
        logger.info(f"[LIVE] CANCELLED {order_id}")
        return True
    except Exception as e:
        logger.error(f"[LIVE] Cancel FAILED {order_id}: {e}")
        return False
