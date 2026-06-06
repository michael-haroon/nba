#!/usr/bin/env python3
"""
NBA Pipeline Production Engine: High-Performance Purification & v2-Unsynced Sync
Author: Gemini Production Framework
Execution: Run as a standalone script in a standard terminal/command line environment.
"""

import os
import glob
import re
import sys
import time
import pandas as pd
from s3fs import S3FileSystem

# --- CONFIGURATION ---
DRY_RUN = False  # Enabled by default. Set to False to execute mutations and uploads.

LOCATIONS = {
    "Local": "/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/data",
    "S3_v1": "s3://nba-265753586044-us-east-1-an/data/v1",
    "S3_curation_root": "s3://nba-265753586044-us-east-1-an/nba/data_curation/data"
}

TARGET_V2_UNSYNCED_PREFIX = "s3://nba-265753586044-us-east-1-an/data/v2-unsynced"

# Explicitly initialize the authenticated S3 file system wrapper globally
S3_FS = S3FileSystem(anon=False)

# Explicit list of allowed dataset bases to process (BPI is intentionally ignored/excluded)
ALLOWED_DATASETS = {
    "AdvBoxScoresAdvPlayoffs", "AdvBoxScoresAdvPre", "AdvBoxScoresAdvRegular",
    "AdvBoxScoresFourFactorsPlayoffs", "AdvBoxScoresFourFactorsPre", "AdvBoxScoresFourFactorsRegular",
    "AdvBoxScoresMiscPlayoffs", "AdvBoxScoresMiscPre", "AdvBoxScoresMiscRegular",
    "AdvBoxScoresScoringPlayoffs", "AdvBoxScoresScoringPre", "AdvBoxScoresScoringRegular",
    "AdvBoxScoresTradPlayoffs", "AdvBoxScoresTradPre", "AdvBoxScoresTradRegular",
    "BoxScoresHustleTeam", "GameOfficials", "GameSummaries", "MasseyRatings",
    "NBAGameIDs", "NBATeams", "PlayerBoxScores", "PlayerStatus", "SagarinRatings",
    "TeamQuarterScores", "nba_arenas_geocoded", "sync_complete"
}

def clean_and_validate_dataframe(df):
    """
    Applies strict data quality purification steps:
    1. Removes columns that are entirely NaN.
    2. Drops exact duplicate rows.
    3. Removes rows that are entirely NaN.
    4. Cleans row leaks where column names were erroneously captured as cell strings.
    5. Removes redundant columns (where both column name AND content match 100%).
    """
    if df.empty:
        return df

    # 1. Column is not entirely nan
    df = df.dropna(axis=1, how='all')
    if df.empty:
        return df

    # 2. Row is not an exact duplicate of another row
    df = df.drop_duplicates()
    if df.empty:
        return df

    # 3. Row is not entirely nan
    df = df.dropna(axis=0, how='all')
    if df.empty:
        return df

    # 4. Row contains data, not header name leaks (Case-insensitive verification)
    is_header_leak = pd.Series(False, index=df.index)
    for col in df.columns:
        cleaned_col_name = str(col).strip().upper()
        is_header_leak = is_header_leak | (df[col].astype(str).str.strip().str.upper() == cleaned_col_name)
    df = df[~is_header_leak]
    if df.empty:
        return df

    # 5. Remove redundant columns (identical column names AND identical data series 100%)
    keep_cols = []
    seen_col_fingerprints = set()
    
    for col in df.columns:
        # Create a unique fingerprint combined of the column name and its underlying data values
        col_name_norm = str(col).strip().upper()
        col_values_tuple = tuple(df[col].astype(str))
        fingerprint = (col_name_norm, col_values_tuple)
        
        if fingerprint not in seen_col_fingerprints:
            seen_col_fingerprints.add(fingerprint)
            keep_cols.append(col)
            
    df = df[keep_cols]
    return df

def profile_dataset(file_path, ext):
    """Ingests file structures across S3 or Local targets safely and applies purification layers."""
    df = pd.DataFrame()
    try:
        if file_path.startswith("s3://"):
            clean_s3_path = file_path.replace("s3://", "")
            if S3_FS.size(clean_s3_path) == 0:
                return {"ext": ext, "valid_rows_count": 0, "valid_rows_str": "0/0 (0.0%)", "df_cached": pd.DataFrame()}
                
            if ext in ['.parquet', '.pq']:
                df = pd.read_parquet(file_path, filesystem=S3_FS)
            elif ext == '.csv':
                with S3_FS.open(clean_s3_path, mode='rb') as f:
                    df = pd.read_csv(f, low_memory=False)
            elif ext == '.tsv':
                with S3_FS.open(clean_s3_path, mode='rb') as f:
                    df = pd.read_csv(f, sep='\t', low_memory=False)
        else:
            if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                return {"ext": ext, "valid_rows_count": 0, "valid_rows_str": "0/0 (0.0%)", "df_cached": pd.DataFrame()}
                
            if ext in ['.parquet', '.pq']:
                df = pd.read_parquet(file_path)
            elif ext == '.csv':
                df = pd.read_csv(file_path, low_memory=False)
            elif ext == '.tsv':
                df = pd.read_csv(file_path, sep='\t', low_memory=False)
    except Exception:
        return {"ext": ext, "valid_rows_count": 0, "valid_rows_str": "0/0 (0.0%)", "df_cached": pd.DataFrame()}

    total_rows = len(df)
    if total_rows == 0:
        return {"ext": ext, "valid_rows_count": 0, "valid_rows_str": "0/0 (0.0%)", "df_cached": pd.DataFrame()}
        
    df_cleaned = clean_and_validate_dataframe(df)
    valid_rows_count = len(df_cleaned)
    valid_pct = round((valid_rows_count / total_rows) * 100, 1)
    
    return {
        "ext": ext,
        "valid_rows_count": valid_rows_count,
        "valid_rows_str": f"{valid_rows_count}/{total_rows} ({valid_pct}%)",
        "df_cached": df_cleaned
    }

def resolve_best_internal_format(variants, base_name, loc_name):
    """
    Evaluates all format variants inside a single source folder location.
    Logs each variant checked, matches row quality counts, and identifies the format winner.
    """
    best_profile = None
    best_ext = None
    best_path = None
    
    print(f"    ↳ Location: [{loc_name}]")
    
    for variant in variants:
        profile = profile_dataset(variant['path'], variant['ext'])
        v_name = os.path.basename(variant['path'])
        print(f"        • Checked variant: {v_name:<45} -> Quality Rows: {profile['valid_rows_str']}")
        
        if best_profile is None:
            best_profile = profile
            best_ext = variant['ext']
            best_path = variant['path']
        else:
            current_max = best_profile['valid_rows_count']
            candidate_val = profile['valid_rows_count']
            
            if candidate_val > current_max:
                best_profile = profile
                best_ext = variant['ext']
                best_path = variant['path']
            elif candidate_val == current_max:
                # Break tie by prioritizing Parquet performance layouts
                if variant['ext'] in ['.parquet', '.pq'] and best_ext not in ['.parquet', '.pq']:
                    best_profile = profile
                    best_ext = variant['ext']
                    best_path = variant['path']
                    
    chosen_file = os.path.basename(best_path) if best_path else "-"
    print(f"        🏆 INTERNAL WINNER for [{loc_name}]: {chosen_file} ({best_profile['valid_rows_count']} rows)")
    return best_profile, best_ext, best_path

def calculate_best_source(local_prof, s1_prof, sroot_prof):
    """Applies structured precedence rules to isolate the absolute best environment source."""
    l_count = local_prof.get("valid_rows_count", -1) if local_prof else -1
    s1_count = s1_prof.get("valid_rows_count", -1) if s1_prof else -1
    sr_count = sroot_prof.get("valid_rows_count", -1) if sroot_prof else -1
    
    max_val = max(l_count, s1_count, sr_count)
    if max_val <= 0:
        return "-"
        
    # Priority Rule: If Local ties for max rows or is the only option, select Local
    if l_count == max_val:
        return "Local"
    # Priority Rule: Break S3 ties using S3_v1
    if s1_count == max_val:
        return "S3_v1"
    return "S3_curation_root"

def save_processed_dataset(df, base_name, source_name):
    """Commits cached data to Local and S3 v2-unsynced partitions securely."""
    ext = ".csv" if base_name == "nba_arenas_geocoded" else ".parquet"
    
    local_dest_dir = LOCATIONS["Local"]
    local_dest_path = os.path.join(local_dest_dir, f"{base_name}{ext}")
    s3_dest_path = f"{TARGET_V2_UNSYNCED_PREFIX}/{base_name}{ext}"
    
    if DRY_RUN:
        print(f"    [DRY RUN] Would read from master source layer: [{source_name}]")
        print(f"    [DRY RUN] Would write local file cache ----> {local_dest_path} ({len(df)} rows)")
        print(f"    [DRY RUN] Would upload cloud S3 packet ----> {s3_dest_path}")
        return
        
    # Local File System Commits
    try:
        os.makedirs(local_dest_dir, exist_ok=True)
        if ext == ".parquet":
            df.to_parquet(local_dest_path, index=False)
        else:
            df.to_csv(local_dest_path, index=False)
        print(f"    ✅ Successfully committed local tracking cache: {local_dest_path}")
    except Exception as e:
        print(f"    ❌ Critical failure writing local workspace path {local_dest_path}: {e}")
        return

    # S3 Storage Layer Commits
    try:
        if ext == ".parquet":
            df.to_parquet(s3_dest_path, filesystem=S3_FS, index=False)
        else:
            clean_path = s3_dest_path.replace("s3://", "")
            with S3_FS.open(clean_path, "w", encoding="utf-8") as f:
                df.to_csv(f, index=False)
        print(f"    ✅ Successfully deployed synchronized asset to S3: {s3_dest_path}")
    except Exception as e:
        print(f"    ❌ Critical failure uploading to S3 tracking block {s3_dest_path}: {e}")

def extract_base_name(file_path):
    basename = os.path.basename(file_path)
    return re.sub(r'\.(parquet|csv|tsv|pq)$', '', basename, flags=re.IGNORECASE)

def get_local_manifest(directory):
    extensions = ["*.parquet", "*.pq", "*.csv", "*.tsv"]
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(directory, "**", ext), recursive=True))
    manifest = {}
    for f in files:
        if os.path.isdir(f): continue
        base = extract_base_name(f)
        if base not in ALLOWED_DATASETS: continue
        _, ext = os.path.splitext(f.lower())
        if base not in manifest: manifest[base] = []
        manifest[base].append({"path": f, "ext": ext})
    return manifest

def get_s3_manifest(s3_path):
    manifest = {}
    clean_prefix = s3_path.rstrip('/')
    try:
        all_objects = S3_FS.glob(f"{clean_prefix}/**/*")
        for obj in all_objects:
            full_s3_path = f"s3://{obj}"
            if S3_FS.isdir(obj) or full_s3_path.endswith('/'): continue
            if not full_s3_path.lower().endswith(('.parquet', '.pq', '.csv', '.tsv')): continue
            base = extract_base_name(full_s3_path)
            if base not in ALLOWED_DATASETS: continue
            _, ext = os.path.splitext(full_s3_path.lower())
            if base not in manifest: manifest[base] = []
            manifest[base].append({"path": full_s3_path, "ext": ext})
    except Exception:
        return {}
    return manifest

def main():
    start_pipeline = time.time()
    print("=" * 115)
    print("                       NBA PIPELINE PRODUCTION ENGINE: GRANULAR MULTI-MATRIX SYNC")
    if DRY_RUN:
        print("                  🚨 DRY RUN MODE ACTIVE: Target write engines are virtualized. 🚨")
    print("=" * 115)
    
    print("\n[PHASE 1] Initializing cross-environment catalog manifests...")
    manifests = {
        "Local": get_local_manifest(LOCATIONS["Local"]),
        "S3_v1": get_s3_manifest(LOCATIONS["S3_v1"]),
        "S3_curation_root": get_s3_manifest(LOCATIONS["S3_curation_root"])
    }
    print(" -> Catalogs fully parsed.")

    print("\n" + "=" * 115)
    print("[PHASE 2] CROSS-ENVIRONMENT RECONCILE & SELECTION ENGINE")
    print("=" * 115)
    
    comparison_records = []
    selected_datasets_to_save = {}
    source_origin_paths = {}
    
    for base in sorted(ALLOWED_DATASETS):
        print(f"\n📁 Dataset: [{base}]")
        
        record = {
            "Dataset (Base)": base,
            "Local (Valid Row Quality)": "-",
            "S3_v1 (Valid Row Quality)": "-",
            "S3_curation_root (Valid Row Quality)": "-",
            "Best Source": "-"
        }
        
        profiles = {"Local": None, "S3_v1": None, "S3_curation_root": None}
        paths = {"Local": None, "S3_v1": None, "S3_curation_root": None}
        
        for loc_name in LOCATIONS.keys():
            variants = manifests[loc_name].get(base)
            if variants:
                # Evaluation of files inside a data source logged instantly here
                profile, _, chosen_path = resolve_best_internal_format(variants, base, loc_name)
                profiles[loc_name] = profile
                paths[loc_name] = chosen_path
                if profile:
                    record[f"{loc_name} (Valid Row Quality)"] = profile["valid_rows_str"]
            else:
                print(f"    ↳ Location: [{loc_name}] -> (No variations found)")
                
        # Calculate the macro winner between sources
        best_source_tag = calculate_best_source(profiles["Local"], profiles["S3_v1"], profiles["S3_curation_root"])
        record["Best Source"] = best_source_tag
        comparison_records.append(record)
        
        print(f"    🏆 CROSS-SOURCE WINNER SELECTION FOR [{base}] ----> 🔥 {best_source_tag} 🔥")
        
        selected_profile = profiles.get(best_source_tag)
        if selected_profile and not selected_profile["df_cached"].empty:
            selected_datasets_to_save[base] = selected_profile["df_cached"]
            source_origin_paths[base] = paths.get(best_source_tag)
            
    # Matrix Output
    df_matrix = pd.DataFrame(comparison_records)
    print("\n\n" + "=" * 115)
    print("### FINAL RECONCILIATION SUMMARY MATRIX ###")
    print("=" * 115)
    print(df_matrix.to_markdown(index=False))
    print()
    
    print("=" * 115)
    print("[PHASE 3] SYNCHRONIZATION AND STORAGE PERSISTENCE TARGETING")
    print("=" * 115)
    
    if not selected_datasets_to_save:
        print("⚠️ Pipeline state evaluation complete: No updated row variants to write.")
    else:
        for base in sorted(selected_datasets_to_save.keys()):
            df_to_save = selected_datasets_to_save[base]
            origin_file = os.path.basename(source_origin_paths[base])
            best_source = next(r["Best Source"] for r in comparison_records if r["Dataset (Base)"] == base)
            print(f"\n💾 Processing Output Pipelines for: [{base}]")
            print(f"    • Source Engine Baseline: {origin_file}")
            save_processed_dataset(df_to_save, base, best_source)
            
    total_time = time.time() - start_pipeline
    print("\n" + "=" * 115)
    print(f"✅ PIPELINE MATRIX PROCESSING COMPLETED SUCCESSFULLY IN {total_time:.2f} SECONDS")
    print("=" * 115)

if __name__ == '__main__':
    main()