"""
Compares nba_api vs our custom scraper for the same game.

Tests BoxScoreSummaryV3 and BoxScoreTraditionalV3 side-by-side.
Prints timing, status, and whether the response data matches.

Run:
    conda run -n pred python test_nba_api_vs_scraper.py
"""

import time
import random

import orjson
import requests
from nba_api.stats.endpoints import BoxScoreSummaryV3, BoxScoreTraditionalV3

# A known good game ID to test with
TEST_GAME_ID = "0022200309"

SUMMARY_URL = "https://stats.nba.com/stats/boxscoresummaryv3"
TRADITIONAL_URL = "https://stats.nba.com/stats/boxscoretraditionalv3"

SCRAPER_HEADERS = {
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

TRADITIONAL_PARAMS = {
    "EndPeriod": 10,
    "EndRange": 28800,
    "RangeType": 0,
    "StartPeriod": 1,
    "StartRange": 0,
}


def divider(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def fetch_scraper(url, params):
    session = requests.Session()
    session.headers.update(SCRAPER_HEADERS)
    t0 = time.perf_counter()
    resp = session.get(url, params=params, timeout=(15, 30))
    elapsed = time.perf_counter() - t0
    return resp.status_code, elapsed, resp.content


def fetch_nba_api(endpoint_cls, **kwargs):
    t0 = time.perf_counter()
    endpoint = endpoint_cls(**kwargs)
    elapsed = time.perf_counter() - t0
    raw = endpoint.get_json()
    return elapsed, raw


def compare_top_level_keys(scraper_bytes, nba_api_json_str, label):
    try:
        scraper_data = orjson.loads(scraper_bytes)
        nba_api_data = orjson.loads(nba_api_json_str)
        scraper_keys = set(scraper_data.keys())
        nba_keys = set(nba_api_data.keys())
        match = scraper_keys == nba_keys
        print(f"  Top-level keys match: {match}")
        if not match:
            print(f"    scraper only: {scraper_keys - nba_keys}")
            print(f"    nba_api only: {nba_keys - scraper_keys}")
    except Exception as e:
        print(f"  Could not compare keys for {label}: {e}")


# =========================================================
# SUMMARY
# =========================================================

divider("BoxScoreSummaryV3 — nba_api")
try:
    elapsed, raw = fetch_nba_api(BoxScoreSummaryV3, game_id=TEST_GAME_ID)
    data = orjson.loads(raw)
    print(f"  Status  : OK")
    print(f"  Elapsed : {elapsed:.2f}s")
    print(f"  Top-level keys: {list(data.keys())}")
    nba_api_summary_raw = raw
except Exception as e:
    print(f"  FAILED: {e}")
    nba_api_summary_raw = None

time.sleep(random.uniform(1.0, 1.5))

divider("BoxScoreSummaryV3 — scraper")
try:
    status, elapsed, content = fetch_scraper(
        SUMMARY_URL, {"GameID": TEST_GAME_ID}
    )
    print(f"  Status  : {status}")
    print(f"  Elapsed : {elapsed:.2f}s")
    if status == 200:
        data = orjson.loads(content)
        print(f"  Top-level keys: {list(data.keys())}")
        if nba_api_summary_raw:
            compare_top_level_keys(content, nba_api_summary_raw, "summary")
    else:
        print(f"  Response snippet: {content[:200]}")
    scraper_summary_content = content if status == 200 else None
except Exception as e:
    print(f"  FAILED: {e}")
    scraper_summary_content = None

time.sleep(random.uniform(1.0, 1.5))

# =========================================================
# TRADITIONAL
# =========================================================

divider("BoxScoreTraditionalV3 — nba_api")
try:
    elapsed, raw = fetch_nba_api(
        BoxScoreTraditionalV3,
        game_id=TEST_GAME_ID,
        end_period=10,
        end_range=28800,
        range_type=0,
        start_period=1,
        start_range=0,
    )
    data = orjson.loads(raw)
    print(f"  Status  : OK")
    print(f"  Elapsed : {elapsed:.2f}s")
    print(f"  Top-level keys: {list(data.keys())}")
    nba_api_trad_raw = raw
except Exception as e:
    print(f"  FAILED: {e}")
    nba_api_trad_raw = None

time.sleep(random.uniform(1.0, 1.5))

divider("BoxScoreTraditionalV3 — scraper")
try:
    trad_params = {"GameID": TEST_GAME_ID, **TRADITIONAL_PARAMS}
    status, elapsed, content = fetch_scraper(TRADITIONAL_URL, trad_params)
    print(f"  Status  : {status}")
    print(f"  Elapsed : {elapsed:.2f}s")
    if status == 200:
        data = orjson.loads(content)
        print(f"  Top-level keys: {list(data.keys())}")
        if nba_api_trad_raw:
            compare_top_level_keys(content, nba_api_trad_raw, "traditional")
    else:
        print(f"  Response snippet: {content[:200]}")
except Exception as e:
    print(f"  FAILED: {e}")

divider("DONE")
