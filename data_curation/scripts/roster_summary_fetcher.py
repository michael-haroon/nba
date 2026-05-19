"""
NBA bulk scraper — multi-threaded, per-thread sessions.
- Hits summary and hustle endpoints

Each worker maintains its own requests.Session using nba_api's exact
headers, proven to work without WAF blocks. Summary is always fetched
before traditional on the same session (warm-session requirement).

Expected Runtime
----------------
~6-9 hours for ~40k games with 3 workers.
Fully resumable — already-downloaded games are skipped.

Run
---
conda run -n pred python roster_summary_fetcher.py
"""

from __future__ import annotations

import concurrent.futures as futures
import logging
import random
import threading
import time
import traceback
from pathlib import Path

import orjson
import pandas as pd
import requests
import zstandard as zstd


# =========================================================
# CONFIG
# =========================================================

GAME_ID_PATH = "../data/nba_game_ids.parquet"

OUTPUT_ROOT = Path("output")
RAW_SUMMARY_DIR = OUTPUT_ROOT / "raw" / "summary"
RAW_TRAD_DIR = OUTPUT_ROOT / "raw" / "traditional"
LOG_DIR = OUTPUT_ROOT / "logs"

RAW_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
RAW_TRAD_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

MAX_WORKERS = 3
MAX_RETRIES = 5

SLEEP_BETWEEN_GAMES = (0.6, 1.2)
SLEEP_BETWEEN_REQUESTS = (0.4, 0.8)
RATE_LIMIT_BACKOFF = (60, 90)
FORBIDDEN_BACKOFF = (120, 150)

SAVE_PROGRESS_EVERY = 100

SUMMARY_URL = "https://stats.nba.com/stats/boxscoresummaryv3"
TRADITIONAL_URL = "https://stats.nba.com/stats/boxscoretraditionalv3"

TRADITIONAL_PARAMS = {
    "EndPeriod": 10,
    "EndRange": 28800,
    "RangeType": 0,
    "StartPeriod": 1,
    "StartRange": 0,
}

# Exact headers from nba_api — do not modify
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Fetch-Dest": "empty",
}


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("nba_scraper")


# =========================================================
# GLOBALS
# =========================================================

thread_local = threading.local()
stats_lock = threading.Lock()
stats = {"success": 0, "failed": 0, "skipped": 0}


# =========================================================
# SESSION (per thread)
# =========================================================

def get_session() -> requests.Session:
    if getattr(thread_local, "session", None) is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        thread_local.session = s
    return thread_local.session


def reset_session():
    thread_local.session = None


# =========================================================
# HELPERS
# =========================================================

def compress_json(data: dict) -> bytes:
    if getattr(thread_local, "compressor", None) is None:
        thread_local.compressor = zstd.ZstdCompressor(level=3)
    return thread_local.compressor.compress(orjson.dumps(data))


def raw_summary_path(game_id: str) -> Path:
    return RAW_SUMMARY_DIR / f"{game_id}.json.zst"


def raw_traditional_path(game_id: str) -> Path:
    return RAW_TRAD_DIR / f"{game_id}.json.zst"


def already_downloaded(game_id: str) -> bool:
    return raw_summary_path(game_id).exists() and raw_traditional_path(game_id).exists()


# =========================================================
# FETCH WITH RETRY
# =========================================================

def fetch_json(url: str, params: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            session = get_session()
            response = session.get(
                url,
                params=sorted(params.items()),
                timeout=(15, 30),
            )
            status = response.status_code

            if status == 200:
                raw = response.content
                if raw.startswith(b"<!DOCTYPE"):
                    raise RuntimeError("HTML_RESPONSE")
                return orjson.loads(raw)

            elif status in (429, 503):
                sleep = random.uniform(*RATE_LIMIT_BACKOFF)
                logger.warning(f"RATE LIMITED ({status}) — backing off {sleep:.0f}s")
                reset_session()
                time.sleep(sleep)

            elif status == 403:
                sleep = random.uniform(*FORBIDDEN_BACKOFF)
                logger.warning(f"FORBIDDEN (403) — backing off {sleep:.0f}s")
                reset_session()
                time.sleep(sleep)

            else:
                sleep = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"BAD STATUS={status} — retrying in {sleep:.2f}s")
                time.sleep(sleep)

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            err = repr(e)
            if "Timeout" in err:
                sleep = random.uniform(*RATE_LIMIT_BACKOFF)
                logger.warning(f"TIMEOUT (soft rate-limit) — backing off {sleep:.0f}s | attempt={attempt+1}")
                reset_session()
            else:
                sleep = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Retrying in {sleep:.2f}s | attempt={attempt+1} | {err}")
            time.sleep(sleep)

    raise RuntimeError("Exhausted retries")


# =========================================================
# GAME PROCESSOR
# =========================================================

def process_game(game_id: str) -> str:
    if already_downloaded(game_id):
        return "skipped"

    try:
        summary_data = fetch_json(SUMMARY_URL, {"GameID": game_id})

        time.sleep(random.uniform(*SLEEP_BETWEEN_REQUESTS))

        trad_data = fetch_json(TRADITIONAL_URL, {"GameID": game_id, **TRADITIONAL_PARAMS})

        with open(raw_summary_path(game_id), "wb") as f:
            f.write(compress_json(summary_data))

        with open(raw_traditional_path(game_id), "wb") as f:
            f.write(compress_json(trad_data))

        return "success"

    except Exception as e:
        logger.error(f"FAILED game_id={game_id} | {e}")
        logger.error(traceback.format_exc())
        return "failed"


# =========================================================
# MAIN
# =========================================================

def main():
    logger.info("Loading game IDs...")

    df = pd.read_parquet(GAME_ID_PATH)
    game_ids = df["GAME_ID"].astype(str).str.zfill(10).unique().tolist()

    logger.info(f"Loaded {len(game_ids):,} unique game IDs")

    remaining = [gid for gid in game_ids if not already_downloaded(gid)]
    skipped_upfront = len(game_ids) - len(remaining)
    if skipped_upfront:
        logger.info(f"Resuming — skipping {skipped_upfront:,} already-downloaded games, {len(remaining):,} remaining")
        stats["skipped"] += skipped_upfront

    started = time.time()

    with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_game = {executor.submit(process_game, gid): gid for gid in remaining}

        for i, future in enumerate(futures.as_completed(future_to_game), start=1):
            game_id = future_to_game[future]
            try:
                result = future.result()
                with stats_lock:
                    stats[result] += 1
                if result == "success":
                    time.sleep(random.uniform(*SLEEP_BETWEEN_GAMES))
            except Exception as e:
                logger.error(f"UNHANDLED FAILURE game_id={game_id} | {repr(e)}")
                with stats_lock:
                    stats["failed"] += 1

            if i % SAVE_PROGRESS_EVERY == 0:
                elapsed = time.time() - started
                rate = i / max(elapsed, 1)
                logger.info(
                    f"Progress={i:,}/{len(remaining):,} | "
                    f"success={stats['success']:,} | "
                    f"failed={stats['failed']:,} | "
                    f"skipped={stats['skipped']:,} | "
                    f"rate={rate:.2f} games/sec"
                )

    elapsed = time.time() - started
    logger.info("=" * 60)
    logger.info("SCRAPE COMPLETE")
    logger.info(f"Elapsed : {elapsed / 60:.2f} mins")
    logger.info(f"Success : {stats['success']:,}")
    logger.info(f"Failed  : {stats['failed']:,}")
    logger.info(f"Skipped : {stats['skipped']:,}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
