"""
This folder is the PINNACLE for using the NBA API. always refer to it as an example
"""

import logging
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm.notebook import tqdm

# --- CONFIGURATION & PATHS ---
DATA_DIR = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data_curation/data")
LOG_DIR = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data_curation/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Output destinations
SUMMARY_OUTPUT = DATA_DIR / "BoxScoresSummary.parquet"
HUSTLE_TEAM_OUTPUT = DATA_DIR / "BoxScoresHustleTeam.parquet"

# Setup clean Jupyter-safe logging
logger = logging.getLogger("nba_boxscore_pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(stream_handler)


# --- API EXTRACTION WORKERS ---
def fetch_single_game_data(game_id_str: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Queries both BoxScoreSummaryV3 and BoxScoreHustleV2 for a given game ID.

    Implements a jittered exponential retry backoff to survive rate-limiting.
    """
    from nba_api.stats.endpoints import boxscorehustlev2, boxscoresummaryv3

    # Ensure 10-digit zero-padded string alignment required by NBA API
    formatted_id = str(game_id_str).zfill(10)

    summary_df = None
    hustle_team_df = None

    # --- PART 1: BOX SCORE SUMMARY V3 ---
    for attempt in range(3):
        try:
            summary = boxscoresummaryv3.BoxScoreSummaryV3(game_id=formatted_id)
            df_summary = summary.game_summary.get_data_frame()
            df_linescore = summary.line_score.get_data_frame()

            if not df_summary.empty and not df_linescore.empty:
                sum_row = df_summary.iloc[0]
                home_id = sum_row.get("homeTeamId")
                away_id = sum_row.get("awayTeamId")

                home_line = df_linescore[df_linescore["teamId"] == home_id]
                away_line = df_linescore[df_linescore["teamId"] == away_id]

                if not home_line.empty and not away_line.empty:
                    hl = home_line.iloc[0]
                    al = away_line.iloc[0]

                    summary_df = pd.DataFrame(
                        [
                            {
                                "game_id": formatted_id,
                                "game_code": sum_row.get("gameCode"),
                                "game_status": sum_row.get("gameStatus"),
                                "game_status_text": sum_row.get("gameStatusText"),
                                "period": sum_row.get("period"),
                                "game_time_utc": sum_row.get("gameTimeUTC"),
                                "game_et": sum_row.get("gameEt"),
                                "game_duration": sum_row.get("duration"),
                                "attendance": sum_row.get("attendance"),
                                "sellout": sum_row.get("sellout"),
                                "home_team_id": int(home_id),
                                "home_team_tricode": hl.get("teamTricode"),
                                "home_team_name": hl.get("teamName"),
                                "home_team_city": hl.get("teamCity"),
                                "home_wins_before": hl.get("teamWins"),
                                "home_losses_before": hl.get("teamLosses"),
                                "home_q1": hl.get("period1Score"),
                                "home_q2": hl.get("period2Score"),
                                "home_q3": hl.get("period3Score"),
                                "home_q4": hl.get("period4Score"),
                                "home_score": hl.get("score"),
                                "away_team_id": int(away_id),
                                "away_team_tricode": al.get("teamTricode"),
                                "away_team_name": al.get("teamName"),
                                "away_team_city": al.get("teamCity"),
                                "away_wins_before": al.get("teamWins"),
                                "away_losses_before": al.get("teamLosses"),
                                "away_q1": al.get("period1Score"),
                                "away_q2": al.get("period2Score"),
                                "away_q3": al.get("period3Score"),
                                "away_q4": al.get("period4Score"),
                                "away_score": al.get("score"),
                            }
                        ]
                    )
                break
        except Exception:
            time.sleep((2**attempt) + random.uniform(0.5, 1.5))

    # --- PART 2: BOX SCORE HUSTLE V2 ---
    # Note: Hustle tracking metrics officially began during the 2016-17 NBA season.
    # Older game historical entries will safely return an empty dataframe without crashing.
    for attempt in range(3):
        try:
            hustle = boxscorehustlev2.BoxScoreHustleV2(game_id=formatted_id)
            df_hustle_team = hustle.team_stats.get_data_frame()

            if not df_hustle_team.empty:
                df_hustle_team = df_hustle_team.copy()
                df_hustle_team["game_id"] = formatted_id
                hustle_team_df = df_hustle_team
                break
        except Exception:
            time.sleep((2**attempt) + random.uniform(0.5, 1.5))

    return summary_df, hustle_team_df


# --- ANALYTICAL DRY-RUN ANALYSIS ---
def execute_pipeline(dry_run: bool = True, batch_size_days: int = 5):
    """Orchestrates checkpoint sync optimization, cross-verifies indices,

    and handles targeted batch extractions with detailed step-by-step telemetry reports.
    """
    logger.info("=== STEP 1: LOADING MASTER GAME SOURCE REGISTER ===")
    parquet_source = DATA_DIR / "nba_game_ids.parquet"

    if not parquet_source.exists():
        logger.error(f"Missing absolute source base file target: {parquet_source}")
        return

    # Ingest baseline register tracking mapping
    master_df = pd.read_parquet(parquet_source)
    # Ensure uniform string zero-padding alignment matching API output schema targets
    master_df["GAME_ID"] = master_df["GAME_ID"].astype(str).str.zfill(10)

    logger.info(f"Loaded master source matrix index: {len(master_df):,} total records.")
    print(master_df.dtypes)

    logger.info("=== STEP 2: ASSESSING EXISTING INCREMENTAL PARQUETS CHECKPOINTS ===")
    existing_summaries = set()
    existing_hustle = set()

    if SUMMARY_OUTPUT.exists():
        ex_sum_df = pd.read_parquet(SUMMARY_OUTPUT, columns=["game_id"])
        existing_summaries = set(ex_sum_df["game_id"].astype(str).str.zfill(10))
        logger.info(
            f"Detected active checkpoint file [BoxScoresSummary.parquet]: {len(existing_summaries):,} games logged."
        )
    else:
        logger.info(
            "No prior checkpoint detected for BoxScoresSummary. Creating a clean tracking instance."
        )

    if HUSTLE_TEAM_OUTPUT.exists():
        ex_hust_df = pd.read_parquet(HUSTLE_TEAM_OUTPUT, columns=["game_id"])
        existing_hustle = set(ex_hust_df["game_id"].astype(str).str.zfill(10))
        logger.info(
            f"Detected active checkpoint file [BoxScoresHustleTeam.parquet]: {len(existing_hustle):,} entries logged."
        )
    else:
        logger.info(
            "No prior checkpoint detected for BoxScoresHustleTeam. Creating a clean tracking instance."
        )

    # Eliminate previously processed game records from execution loop map
    # A game is completed only if it has been verified inside our checkpoint data registers
    needed_games_df = master_df[
        ~(master_df["GAME_ID"].isin(existing_summaries))
        | (
            ~(master_df["GAME_ID"].isin(existing_hustle))
            & (master_df["GAME_DATE"] >= "2016-10-01")
        )
    ].copy()

    logger.info(
        f"Filtered Backlog Remaining to Process: {len(needed_games_df):,} target games require update processing."
    )

    if needed_games_df.empty:
        logger.info("🎉 Database system checks indicate synchronization is complete!")
        return

    # Group execution queue sequentially by actual calendar date bounds
    needed_games_df["GAME_DATE_STR"] = (
        needed_games_df["GAME_DATE"].dt.strftime("%Y-%m-%d").astype(str)
    )
    unique_days = sorted(needed_games_df["GAME_DATE_STR"].unique())

    if dry_run:
        logger.info("======================================================")
        logger.info("📊               DRY-RUN ANALYSIS REPORT              ")
        logger.info("======================================================")
        logger.info(f"Total Games in Master Inventory Index: {len(master_df):,}")
        logger.info(f"Cached Game Summaries:                 {len(existing_summaries):,}")
        logger.info(f"Cached Hustle Game Logs:               {len(existing_hustle):,}")
        logger.info(f"Net Remaining Games Queue:             {len(needed_games_df):,}")
        logger.info(f"Total Unique Calendar Match Days:      {len(unique_days):,}")

        print("\n--- SAMPLE VIEW: RETRIEVAL BACKLOG QUEUE TARGETS ---")
        display(needed_games_df.head(5))

        logger.info("=== SIMULATING PIPELINE EXTRACTION STEP ON 1 TARGET GAME ===")
        sample_id = needed_games_df["GAME_ID"].iloc[0]
        logger.info(f"Executing trial api pull for test ID: {sample_id}")

        test_sum, test_hust = fetch_single_game_data(sample_id)

        print("\n[DRY RUN PROJECTION] Mock Row Counts at Step Completion:")
        if test_sum is not None:
            print(
                f" -> BoxScoresSummary Change: {len(existing_summaries):,} -> {len(existing_summaries) + 1:,}"
            )
            print("\n--- EXTRACTED DATA SAMPLE: SUMMARY ROW TRANSFORMATION ---")
            display(test_sum)
        else:
            print(" -> BoxScoresSummary Change: 0 (API target item mismatch or null payload)")

        if test_hust is not None:
            print(
                f" -> BoxScoresHustleTeam Change: {len(existing_hustle):,} -> {len(existing_hustle) + len(test_hust):,}"
            )
            print("\n--- EXTRACTED DATA SAMPLE: HUSTLE TEAM ROW TRANSFORMATION ---")
            display(test_hust)
        else:
            print(
                " -> BoxScoresHustleTeam Change: 0 (Game occurs pre-2016 or returned null stats)"
            )

        logger.info("======================================================")
        logger.info("Dry run simulation analysis complete. Set dry_run=False to execute.")
        return

    # --- ACTION EXECUTION WORK BRACKET ---
    logger.info(
        f"Bypassing safe trial parameters. Starting multi-threaded download run in blocks of {batch_size_days} calendar days..."
    )

    # Process chunks of calendar dates together
    for i in range(0, len(unique_days), batch_size_days):
        day_chunk = unique_days[i : i + batch_size_days]
        chunk_games = needed_games_df[needed_games_df["GAME_DATE_STR"].isin(day_chunk)][
            "GAME_ID"
        ].unique()

        logger.info(
            f"Processing date bracket block [{day_chunk[0]} to {day_chunk[-1]}]: Gathering {len(chunk_games)} target items..."
        )

        accumulated_summaries = []
        accumulated_hustle = []

        # ThreadPoolExecutor scales network extraction efficiently without overloading the engine
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_game = {
                executor.submit(fetch_single_game_data, gid): gid for gid in chunk_games
            }

            for future in tqdm(
                as_completed(future_to_game),
                total=len(chunk_games),
                desc=f"Batch Block ({day_chunk[0]})",
                leave=False,
            ):
                try:
                    s_df, h_df = future.result()
                    if s_df is not None:
                        accumulated_summaries.append(s_df)
                    if h_df is not None:
                        accumulated_hustle.append(h_df)
                except Exception as err:
                    gid = future_to_game[future]
                    logger.error(f"Uncaught task error handling game record {gid}: {err}")

                # Gentle request tracking delay throttle
                time.sleep(random.uniform(0.4, 0.9))

        # --- CONSOLIDATING BATCH CHECKPOINTS AND RE-SAVING PARQUET ON DISK ---
        if accumulated_summaries:
            new_sum_df = pd.concat(accumulated_summaries, ignore_index=True)
            if SUMMARY_OUTPUT.exists():
                old_sum_df = pd.read_parquet(SUMMARY_OUTPUT)
                combined_sum = pd.concat([old_sum_df, new_sum_df], ignore_index=True)
                # Drop duplicate IDs to prevent downstream analytical pollution
                combined_sum = combined_sum.drop_duplicates(subset=["game_id"], keep="last")
            else:
                combined_sum = new_sum_df
            combined_sum.to_parquet(SUMMARY_OUTPUT, index=False)
            logger.info(
                f" Updated Checkpoint [BoxScoresSummary.parquet] size is now: {len(combined_sum):,} rows."
            )

        if accumulated_hustle:
            new_hust_df = pd.concat(accumulated_hustle, ignore_index=True)
            if HUSTLE_TEAM_OUTPUT.exists():
                old_hust_df = pd.read_parquet(HUSTLE_TEAM_OUTPUT)
                combined_hust = pd.concat([old_hust_df, new_hust_df], ignore_index=True)
                # Hustle tables store 2 rows per game (one per team), deduplicate across both variables
                combined_hust = combined_hust.drop_duplicates(
                    subset=["game_id", "TEAM_ID"], keep="last"
                )
            else:
                combined_hust = new_hust_df
            combined_hust.to_parquet(HUSTLE_TEAM_OUTPUT, index=False)
            logger.info(
                f" Updated Checkpoint [BoxScoresHustleTeam.parquet] size is now: {len(combined_hust):,} rows."
            )

        # Main rate limiting pause between daily block writes to avoid server penalties
        time.sleep(random.uniform(1.5, 3.0))


# --- RUN PIPELINE ---
# Step 1: Run analytical dry run first to visually check output transformations
execute_pipeline(dry_run=True)

# Step 2: Once you verify the output profiles look correct, uncomment line below to start full collection
# execute_pipeline(dry_run=False, batch_size_days=3)