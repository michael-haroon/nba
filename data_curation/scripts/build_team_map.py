import pandas as pd
import requests
import logging
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from nba_api.stats.endpoints import leaguegamefinder

# --- DIRECTORY SETUP ---
ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
DATA_DIR = ROOT_DIR / "data"

LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "team_discovery.log"),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)

def get_all_nba_teams_history(start_year=1946):
    """Scans all seasons in NBA history for unique team entries."""
    all_teams = []
    current_year = datetime.now().year
    
    logger.info(f"Starting NBA historical scan from {start_year}...")
    
    for y in range(start_year, current_year + 1):
        season_str = f"{y}-{str(y+1)[-2:]}"
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season_str, 
                league_id_nullable="00"
            )
            df = finder.get_data_frames()[0]
            if not df.empty:
                teams = df[["TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME"]].copy()
                # Precision Fix: Convert to string immediately to avoid scientific notation
                teams["TEAM_ID"] = teams["TEAM_ID"].astype(str)
                teams = teams.drop_duplicates()
                teams["first_seen_season"] = season_str
                all_teams.append(teams)
                logger.info(f"Retrieved {len(teams)} NBA teams for {season_str}")
            time.sleep(0.8) # Slight delay to respect NBA API rate limits
        except Exception as e:
            logger.error(f"Failed NBA scan for {season_str}: {e}")
            
    # keep='last' ensures modern names (Wizards) overwrite old names (Bullets)
    combined = pd.concat(all_teams).drop_duplicates(subset=["TEAM_ID"], keep='last')
    combined.to_csv(DATA_DIR / "nba_team_candidates.csv", index=False)
    logger.info(f"NBA Scan Complete: Saved {len(combined)} teams.")
    return combined

def get_all_espn_teams_history(start_year=2000):
    """Scans ESPN standings API."""
    all_espn = []
    current_year = datetime.now().year
    url = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    
    logger.info(f"Starting ESPN historical scan from {start_year}...")
    
    for y in range(start_year, current_year + 1):
        try:
            r = requests.get(url, params={"season": y}, timeout=15)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                for group in data.get("children", []):
                    for entry in group.get("standings", {}).get("entries", []):
                        t = entry.get("team", {})
                        all_espn.append({
                            "ESPN_ID": str(t.get("id")),
                            "ESPN_ABBR": t.get("abbreviation"),
                            "ESPN_NAME": t.get("displayName"),
                            "year": y
                        })
                logger.info(f"Retrieved ESPN teams for year {y}")
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Failed ESPN scan for year {y}: {e}")
            
    espn_df = pd.DataFrame(all_espn).drop_duplicates(subset=["ESPN_ID", "ESPN_ABBR"], keep='last')
    espn_df.to_csv(DATA_DIR / "espn_team_candidates.csv", index=False)
    logger.info(f"ESPN Scan Complete: Saved {len(espn_df)} teams.")
    return espn_df

if __name__ == "__main__":
    start_time = time.time()
    
    # Use ThreadPoolExecutor to run both API scans in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Launch both tasks
        # nba_task = executor.submit(get_all_nba_teams_history, 1946)
        espn_task = executor.submit(get_all_espn_teams_history, 1946)
        
        # Wait for both to finish and collect results
        # nba_results = nba_task.result()
        espn_results = espn_task.result()

    total_time = time.time() - start_time
    logger.info(f"Full parallel discovery finished in {total_time:.2f} seconds.")
