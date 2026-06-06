import os
import sys
import time
import json
import random
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from nba_api.stats.endpoints import BoxScoreSummaryV3

# --- CONFIGURATION ---
DATA_DIR = Path('/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/data/raw_payloads/summary')
LOG_PATH = Path('/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/logs/summary.log')
DATA_DIR.mkdir(parents=True, exist_ok=True)

WORKERS = 12
SESSION_RESET_INTERVAL = 25

HEADERS = {
    "Host": "stats.nba.com",
    "Connection": "close",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nba.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.nba.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1"
}

# Explicit logger (avoids basicConfig no-op if logging already initialized)
logger = logging.getLogger("get_summary")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.addHandler(logging.FileHandler(LOG_PATH, mode='a', encoding='utf-8'))
    for h in logger.handlers:
        h.setFormatter(logging.Formatter("%(message)s"))


def log_message(game_id, status, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    logger.info(f"[{timestamp}] [Game: {game_id}] [{status}] {message}")


def fetch_summary_unrelenting(args):
    game_id, index = args
    output_path = DATA_DIR / f"{game_id}_summary.json"

    if index > 0 and index % SESSION_RESET_INTERVAL == 0:
        log_message(game_id, "SESSION", f"Resetting session after {SESSION_RESET_INTERVAL} games. Pausing 5s...")
        time.sleep(5)

    retries = 0
    success = False

    while not success:
        try:
            time.sleep(random.uniform(2.5, 5.0))
            log_message(game_id, "FETCHING", f"Requesting summary payload (Attempt {retries + 1})...")

            summary = BoxScoreSummaryV3(
                game_id=game_id,
                headers=HEADERS,
                timeout=18
            )

            raw_payload = summary.nba_response.get_json()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(raw_payload, f, ensure_ascii=False)

            log_message(game_id, "SUCCESS", f"Saved raw payload to {output_path.name}")
            success = True
            return True

        except AttributeError:
            log_message(game_id, "NO_DATA", "API returned no data for this game. Skipping permanently.")
            output_path.touch()
            return True

        except Exception as e:
            retries += 1
            base_wait = random.uniform(30.0, 60.0)
            wait_penalty = base_wait * (1.5 ** min(retries, 6))
            log_message(game_id, "ERROR", f"Exception: {str(e)}. Cooling down {wait_penalty:.2f}s...")
            if wait_penalty > 60:
                log_message(game_id, "RESTART", f"Hard block detected (cooldown {wait_penalty:.2f}s > 60s). Restarting process...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            time.sleep(wait_penalty)


# --- EXECUTION ---
if __name__ == "__main__":
    SOURCE_IDS_PARQUET = Path('/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/data/NBAGameIDs.parquet')

    if not SOURCE_IDS_PARQUET.exists():
        print(f"[CRITICAL ERROR] Source file not found: {SOURCE_IDS_PARQUET}")
        sys.exit(1)

    games_df = pd.read_parquet(SOURCE_IDS_PARQUET)
    game_ids = games_df['GAME_ID'].astype(str).str.zfill(10).tolist()

    existing_files = {f.name.split('_')[0] for f in DATA_DIR.glob('*_summary.json')}
    game_ids = [gid for gid in game_ids if gid not in existing_files]

    # Process newest games first
    game_ids = game_ids[::-1]

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Launching summary engine. Queue: {len(game_ids)} games. Log: {LOG_PATH}")

    indexed_swapped = [(gid, i) for i, gid in enumerate(game_ids)]

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        executor.map(fetch_summary_unrelenting, indexed_swapped)

    print("All summary tasks processed.")
