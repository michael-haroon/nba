"""
download_kalshi_history.py
---------------------------
Historical Kalshi NBA market archive: per-game series candlesticks, from market
open through settlement, for every settled market across the 6 real per-game
NBA series (see trading.models.MODEL_TO_SERIES).

Ported from mlb/data_curation/scripts/download_kalshi_history.py +
download_kalshi_historical.py, collapsed into one script since NBA's per-series
market counts (hundreds, not tens of thousands) don't need two separate
threaded/checkpointed passes.

Two discovery paths, tried in order per series:
  1. LIVE window: GET /markets?series_ticker=X&status=settled — only surfaces
     a recent rolling window (see GET /historical/cutoff).
  2. HISTORICAL (event-driven): GET /events (no status filter) lists event
     shells for all dates, then GET /historical/markets?event_ticker=X returns
     that event's real market(s). This is the only way to reach markets that
     aged out of the live window.

Candles: tries the live per-series endpoint first (only works while the
market is within Kalshi's live window), falls back to the /historical/
candlesticks endpoint (works for any settled market regardless of age).

Checkpointed by market ticker so a killed/restarted run resumes.

Storage: S3 by default, --local for disk. Mirrors MLB's layout:
  s3://nba-265753586044-us-east-1-an/kalshi_history/<SERIES>/candlesticks_batch_*.parquet
  s3://nba-265753586044-us-east-1-an/kalshi_history/<SERIES>/historical/candlesticks_batch_*.parquet

Run:
    python3.11 backtest/download_kalshi_history.py                    # dry run, discovery only
    python3.11 backtest/download_kalshi_history.py --live             # full pull, all series
    python3.11 backtest/download_kalshi_history.py --live --series KXNBAGAME
    python3.11 backtest/download_kalshi_history.py --live --retry
    python3.11 backtest/download_kalshi_history.py --local            # write to disk instead of S3
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT))

from backtest.kalshi_client import make_client  # noqa: E402
from trading.models import MODEL_TO_SERIES  # noqa: E402

SERIES_TICKERS = sorted({s for s in MODEL_TO_SERIES.values() if s})
MAX_WORKERS = 8
RATE_LIMIT_DELAY = 0.15  # adaptive from here, same backoff scheme as the MLB downloader
CANDLE_PERIOD_INTERVAL_MIN = 1
MAX_CANDLES_PER_REQUEST = 4900  # margin under Kalshi's 5000-period cap
MARKET_FLUSH_THRESHOLD = 200
DATA_FLUSH_THRESHOLD = 5000
SUBMIT_BATCH_SIZE = 100

S3_BUCKET = "nba-265753586044-us-east-1-an"
S3_PREFIX = "kalshi_history"
S3_REGION = "us-east-1"
USE_S3 = True
_s3_client = None

DATA_DIR = "data"
LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("KALSHI_HISTORY")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(LOG_DIR, "kalshi_history.log"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s"))
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("[KALSHI HISTORY] %(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# STORAGE LAYER
# ---------------------------------------------------------------------------
def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=S3_REGION)
    return _s3_client


def _s3_key(rel_path: str) -> str:
    return f"{S3_PREFIX}/{rel_path}"


def _read_json_store(rel_path: str):
    if USE_S3:
        try:
            obj = _get_s3().get_object(Bucket=S3_BUCKET, Key=_s3_key(rel_path))
            return json.loads(obj["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
    else:
        local = os.path.join(DATA_DIR, rel_path)
        if not os.path.exists(local):
            return None
        with open(local) as f:
            return json.load(f)


def _write_json_store(rel_path: str, data: Any):
    if USE_S3:
        _get_s3().put_object(
            Bucket=S3_BUCKET, Key=_s3_key(rel_path),
            Body=json.dumps(data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
    else:
        local = os.path.join(DATA_DIR, rel_path)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        tmp = local + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, local)


def _save(df: pd.DataFrame, rel_path: str):
    if df.empty:
        return
    if USE_S3:
        key = _s3_key(rel_path)
        buf = io.BytesIO()
        df.to_parquet(buf, engine="pyarrow", compression="snappy", index=False)
        buf.seek(0)
        _get_s3().put_object(Bucket=S3_BUCKET, Key=key, Body=buf.getvalue())
        logger.debug(f"[save] {len(df)} rows -> s3://{S3_BUCKET}/{key}")
    else:
        full = os.path.join(DATA_DIR, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        df.to_parquet(full, engine="pyarrow", compression="snappy", index=False)
        logger.debug(f"[save] {len(df)} rows -> {full}")


def save_markets(records: List[Dict[str, Any]], series_ticker: str, historical: bool):
    if not records:
        return
    sub = "historical/" if historical else ""
    _save(pd.DataFrame(records), f"{series_ticker}/{sub}markets_batch_{int(time.time()*1000)}.parquet")


def save_candlesticks(records: List[Dict[str, Any]], series_ticker: str, historical: bool):
    if not records:
        return
    sub = "historical/" if historical else ""
    _save(pd.json_normalize(records, sep="_"), f"{series_ticker}/{sub}candlesticks_batch_{int(time.time()*1000)}.parquet")


# ---------------------------------------------------------------------------
# CHECKPOINT MANAGER — keyed by market ticker
# ---------------------------------------------------------------------------
class CheckpointManager:
    def __init__(self, prefix: str = ""):
        self.checkpoint_rel = f"{prefix}checkpoint.json"
        self.retry_rel = f"{prefix}retry_queue.json"
        self._lock = threading.Lock()
        self.completed: Set[str] = set()
        self.retry_queue: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        data = _read_json_store(self.checkpoint_rel)
        if data:
            self.completed = set(data.get("completed", []))
            logger.info(f"[checkpoint] Loaded {len(self.completed)} completed tickers from {self.checkpoint_rel}.")
        retry_data = _read_json_store(self.retry_rel)
        if retry_data:
            self.retry_queue = retry_data
            logger.info(f"[checkpoint] Loaded {len(self.retry_queue)} tickers in {self.retry_rel}.")

    def is_completed(self, ticker: str) -> bool:
        return ticker in self.completed

    def mark_completed(self, ticker: str):
        with self._lock:
            self.completed.add(ticker)
            self._flush_checkpoint()

    def mark_failed(self, ticker: str, series_ticker: str, reason: str, error: str):
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            existing = {e["ticker"]: e for e in self.retry_queue}
            if ticker in existing:
                e = existing[ticker]
                e["attempts"] += 1; e["last_error"] = error
                e["reason"] = reason; e["last_failed"] = now
            else:
                self.retry_queue.append({
                    "ticker": ticker, "series_ticker": series_ticker, "reason": reason,
                    "attempts": 1, "last_error": error,
                    "first_failed": now, "last_failed": now,
                })
            self._flush_retry()

    def clear_retry_entry(self, ticker: str):
        with self._lock:
            self.retry_queue = [e for e in self.retry_queue if e["ticker"] != ticker]
            self.completed.add(ticker)
            self._flush_checkpoint()
            self._flush_retry()

    def get_retry_markets(self) -> List[Dict[str, Any]]:
        return [{"ticker": e["ticker"], "series_ticker": e["series_ticker"]} for e in self.retry_queue]

    def discard_retry_entry(self, ticker: str):
        with self._lock:
            self.retry_queue = [e for e in self.retry_queue if e["ticker"] != ticker]
            self._flush_retry()

    def _flush_checkpoint(self):
        _write_json_store(self.checkpoint_rel, {
            "completed": sorted(self.completed),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })

    def _flush_retry(self):
        _write_json_store(self.retry_rel, self.retry_queue)


# ---------------------------------------------------------------------------
# RATE LIMITER — same adaptive backoff scheme as the MLB downloader.
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, initial_delay: float, min_delay: float = 0.02, max_delay: float = 1.0):
        self.delay = initial_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last = 0.0
        self._lock = threading.Lock()
        self._success_streak = 0

    def wait(self):
        with self._lock:
            now = time.time()
            wait = max(0.0, self._last + self.delay - now)
            self._last = now + wait
        if wait:
            time.sleep(wait)

    def on_429(self):
        with self._lock:
            self.delay = min(self.max_delay, self.delay * 1.5)
            self._success_streak = 0

    def on_success(self):
        with self._lock:
            self._success_streak += 1
            if self._success_streak >= 50:
                self._success_streak = 0
                self.delay = max(self.min_delay, self.delay * 0.9)


_rate_limiter = RateLimiter(RATE_LIMIT_DELAY)


def _call_with_backoff(label: str, fn, *args, **kwargs):
    max_retries = 5
    backoff_factor = 2.0
    for attempt in range(max_retries):
        try:
            _rate_limiter.wait()
            resp = fn(*args, **kwargs)
            _rate_limiter.on_success()
            return resp
        except Exception as e:
            is_429 = "429" in str(e)
            if is_429:
                _rate_limiter.on_429()
            if attempt == max_retries - 1:
                logger.error(f"[{label}] failed after {max_retries} attempts: {e}")
                raise
            sleep_time = backoff_factor ** attempt
            logger.warning(f"[{label}] error: {e}. retry in {sleep_time}s")
            time.sleep(sleep_time)
    raise RuntimeError(f"[{label}] exhausted retries")


def _ts(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    return int(datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp())


# ---------------------------------------------------------------------------
# DISCOVERY
# ---------------------------------------------------------------------------
def discover_live_markets(client, series_ticker: str) -> List[Dict[str, Any]]:
    """Paginate /markets?series_ticker=X&status=settled until cursor exhausts."""
    markets: List[Dict[str, Any]] = []
    cursor = None
    page = 0
    while True:
        resp = _call_with_backoff(
            f"discover:{series_ticker}", client.get_markets,
            series_ticker=series_ticker, status="settled", limit=200, cursor=cursor,
        )
        batch = resp.get("markets", [])
        markets.extend(batch)
        page += 1
        cursor = resp.get("cursor")
        logger.debug(f"[discover:{series_ticker}] page={page} batch={len(batch)} total={len(markets)} cursor={cursor!r}")
        if not cursor or not batch:
            break
    return markets


def discover_historical_events(client, series_ticker: str) -> List[str]:
    """Event-driven discovery for markets that aged out of the live window."""
    events: List[Dict[str, Any]] = []
    cursor = None
    page = 0
    while True:
        resp = _call_with_backoff(
            f"events:{series_ticker}", client.get_events,
            series_ticker=series_ticker, limit=200, cursor=cursor,
        )
        batch = resp.get("events", [])
        events.extend(batch)
        cursor = resp.get("cursor")
        page += 1
        logger.debug(f"[events:{series_ticker}] page={page} total={len(events)}")
        if not cursor or not batch:
            break
    return sorted(e["event_ticker"] for e in events if e.get("event_ticker"))


def discover_historical_markets(client, series_ticker: str, event_tickers: List[str]) -> List[Dict[str, Any]]:
    markets: List[Dict[str, Any]] = []
    for et in event_tickers:
        resp = _call_with_backoff(f"hist-markets:{et}", client.get_historical_markets, event_ticker=et)
        markets.extend(resp.get("markets", []))
    return markets


# ---------------------------------------------------------------------------
# CANDLESTICK FETCH — live endpoint first, historical endpoint as fallback.
# ---------------------------------------------------------------------------
def fetch_candlesticks_for_market(client, series_ticker: str, market: Dict[str, Any],
                                   historical: bool = False) -> List[Dict[str, Any]]:
    ticker = market["ticker"]
    start_ts = _ts(market.get("open_time"))
    end_ts = _ts(market.get("close_time")) or _ts(market.get("expiration_time"))
    if start_ts is None or end_ts is None:
        logger.warning(f"[candles:{ticker}] missing open_time/close_time — skipping")
        return []

    step_seconds = MAX_CANDLES_PER_REQUEST * 60 * CANDLE_PERIOD_INTERVAL_MIN
    windows = []
    cur = start_ts
    while cur < end_ts:
        nxt = min(cur + step_seconds, end_ts)
        windows.append((cur, nxt))
        cur = nxt + 60 * CANDLE_PERIOD_INTERVAL_MIN

    all_candles: List[Dict[str, Any]] = []
    for s, e in windows:
        # Markets discovered via the event-driven historical path have already aged
        # out of Kalshi's live rolling window (confirmed: the live endpoint 404s on
        # every one of them) — go straight to /historical/ and skip the wasted
        # 5-retry backoff on a call that can never succeed for these tickers.
        if historical:
            resp = _call_with_backoff(
                f"hist-candles:{ticker}", client.get_historical_candlesticks,
                ticker, s, e, period_interval=CANDLE_PERIOD_INTERVAL_MIN,
            )
        else:
            try:
                resp = _call_with_backoff(
                    f"candles:{ticker}", client.get_candlesticks,
                    series_ticker, ticker, s, e, period_interval=CANDLE_PERIOD_INTERVAL_MIN,
                )
            except Exception:
                resp = _call_with_backoff(
                    f"hist-candles:{ticker}", client.get_historical_candlesticks,
                    ticker, s, e, period_interval=CANDLE_PERIOD_INTERVAL_MIN,
                )
        all_candles.extend(resp.get("candlesticks", []))

    for c in all_candles:
        c["market_ticker"] = ticker
        c["series_ticker"] = series_ticker
    return all_candles


# ---------------------------------------------------------------------------
# MAIN CRAWL
# ---------------------------------------------------------------------------
def run_series(client, series_ticker: str, checkpoint: CheckpointManager, is_retry: bool = False):
    if is_retry:
        targets = [m for m in checkpoint.get_retry_markets() if m["series_ticker"] == series_ticker]
        if not targets:
            return
        markets = []
        for t in targets:
            try:
                resp = _call_with_backoff(f"retry-refetch:{t['ticker']}", client.get_market, t["ticker"])
            except Exception as e:
                logger.warning(f"[retry-refetch:{series_ticker}] {t['ticker']} unresolvable, dropping: {e}")
                checkpoint.discard_retry_entry(t["ticker"])
                continue
            m = resp.get("market")
            if m:
                markets.append(m)
        historical = False
    else:
        markets = discover_live_markets(client, series_ticker)
        historical = False
        if not markets:
            logger.info(f"[{series_ticker}] 0 settled markets in the live window — trying event-driven historical discovery")
            events = discover_historical_events(client, series_ticker)
            logger.info(f"[{series_ticker}] {len(events)} events found")
            if events:
                markets = discover_historical_markets(client, series_ticker, events)
                historical = True
        if not markets:
            logger.info(f"[{series_ticker}] no settled markets found via either path")
            return
        close_times = sorted(m.get("close_time") for m in markets if m.get("close_time"))
        if close_times:
            logger.info(
                f"[{series_ticker}] {len(markets)} settled markets (historical={historical}) | "
                f"close_time range: {close_times[0]} .. {close_times[-1]}"
            )
        markets = [m for m in markets if not checkpoint.is_completed(m["ticker"])]
        logger.info(f"[{series_ticker}] {len(markets)} pending after checkpoint filter")

    if not markets:
        return

    market_buf: List[Dict[str, Any]] = []
    data_buf: List[Dict[str, Any]] = []
    pending: List[str] = []

    def _flush(label: str):
        if not pending:
            return
        try:
            save_markets(market_buf, series_ticker, historical)
            save_candlesticks(data_buf, series_ticker, historical)
            for ticker in pending:
                if is_retry:
                    checkpoint.clear_retry_entry(ticker)
                else:
                    checkpoint.mark_completed(ticker)
            logger.debug(f"[flush:{series_ticker}:{label}] checkpointed {len(pending)} markets")
        except Exception as e:
            logger.error(f"[flush:{series_ticker}:{label}] save failed: {e}", exc_info=True)
            for ticker in pending:
                checkpoint.mark_failed(ticker, series_ticker, type(e).__name__, str(e))
            raise
        finally:
            market_buf.clear(); data_buf.clear(); pending.clear()

    pbar = tqdm(total=len(markets), desc=f"{series_ticker} ({'retry' if is_retry else 'historical' if historical else 'live'})")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix=f"Kalshi-{series_ticker}") as executor:
        market_iter = iter(markets)
        in_flight: Dict = {}

        def _fill_queue():
            while len(in_flight) < SUBMIT_BATCH_SIZE:
                m = next(market_iter, None)
                if m is None:
                    break
                f = executor.submit(fetch_candlesticks_for_market, client, series_ticker, m, historical)
                in_flight[f] = m

        _fill_queue()
        while in_flight:
            future = next(as_completed(in_flight))
            m = in_flight.pop(future)
            ticker = m["ticker"]
            try:
                records = future.result()
                market_buf.append(m)
                data_buf.extend(records)
                pending.append(ticker)
                pbar.update(1)
                pbar.set_postfix({"candles": len(data_buf), "pending": len(pending)})
                if len(data_buf) >= DATA_FLUSH_THRESHOLD or len(market_buf) >= MARKET_FLUSH_THRESHOLD:
                    _flush("threshold")
            except Exception as e:
                logger.error(f"[{series_ticker}] worker failed for {ticker}: {e}")
                checkpoint.mark_failed(ticker, series_ticker, type(e).__name__, str(e))
                pbar.update(1)
            _fill_queue()
    pbar.close()
    _flush("final")


def dry_run(client):
    logger.info("=== DRY RUN: discovery only, no writes ===")
    for series_ticker in SERIES_TICKERS:
        markets = discover_live_markets(client, series_ticker)
        historical = False
        if not markets:
            events = discover_historical_events(client, series_ticker)
            logger.info(f"[{series_ticker}] 0 live-window markets, {len(events)} historical events")
            if events:
                markets = discover_historical_markets(client, series_ticker, events[:5])
                historical = True
        if not markets:
            logger.info(f"[{series_ticker}] 0 settled markets found via either path")
            continue
        close_times = sorted(m.get("close_time") for m in markets if m.get("close_time"))
        logger.info(
            f"[{series_ticker}] {len(markets)} settled markets sampled (historical={historical}) | "
            f"close_time range: {close_times[0] if close_times else None} .. {close_times[-1] if close_times else None}"
        )
        sample = markets[0]
        logger.info(f"[{series_ticker}] sample market fields: {list(sample.keys())}")
        records = fetch_candlesticks_for_market(client, series_ticker, sample, historical)
        logger.info(f"[{series_ticker}] sample candle count: {len(records)}")
        if records:
            logger.info(f"[{series_ticker}] sample candle fields: {list(records[0].keys())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Historical Kalshi NBA market archive.")
    parser.add_argument("--live", action="store_true", help="Disable dry run and pull + persist all settled markets.")
    parser.add_argument("--retry", action="store_true", help="Process only markets in the retry queue.")
    parser.add_argument("--local", action="store_true", help="Write to local disk instead of S3.")
    parser.add_argument("--series", type=str, default=None, help="Comma-separated series tickers to restrict to.")
    parser.add_argument("--env", type=str, default="prod", choices=["prod", "demo"])
    args = parser.parse_args()

    USE_S3 = not args.local
    if args.series:
        SERIES_TICKERS = [s.strip() for s in args.series.split(",")]

    dest = f"s3://{S3_BUCKET}/{S3_PREFIX}/" if USE_S3 else f"{DATA_DIR}/"
    client = make_client(env=args.env)

    if not args.live and not args.retry:
        logger.info(f"=== KALSHI HISTORY DRY RUN | series={SERIES_TICKERS} ===")
        dry_run(client)
    else:
        checkpoint = CheckpointManager()
        if args.retry:
            logger.info(f"=== RETRY MODE | dest={dest} ===")
            for s in SERIES_TICKERS:
                run_series(client, s, checkpoint, is_retry=True)
        else:
            logger.info(f"=== FULL HISTORICAL PULL | dest={dest} | series={SERIES_TICKERS} ===")
            for s in SERIES_TICKERS:
                run_series(client, s, checkpoint, is_retry=False)
        logger.info("=== DONE ===")
