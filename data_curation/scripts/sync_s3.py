import os
import glob
import re
import sys
import contextlib
import pandas as pd
import boto3
from s3fs import S3FileSystem

# --- CONFIGURATION ---
DRY_RUN = True  # Set to False to actually execute file writes and S3 uploads

LOCATIONS = {
    "Local": "/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/data",
    "S3_v1": "s3://nba-265753586044-us-east-1-an/data/v1",
    "S3_curation_root": "s3://nba-265753586044-us-east-1-an/nba/data_curation/data"
}

TARGET_V2_PREFIX = "s3://nba-265753586044-us-east-1-an/data/v2"

# Explicitly initialize the authenticated S3 file system wrapper globally
S3_FS = S3FileSystem(anon=False)

def extract_base_name(file_path):
    """Extracts the base file name, ignoring the extension and pathing."""
    basename = os.path.basename(file_path)
    base_name_clean = re.sub(r'\.(parquet|csv|tsv|pq)$', '', basename, flags=re.IGNORECASE)
    return base_name_clean

def get_local_manifest(directory):
    """Scans local data files and extracts all matching path metadata variants."""
    extensions = ["*.parquet", "*.pq", "*.csv", "*.tsv"]
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(directory, "**", ext), recursive=True))
    
    manifest = {}
    for f in files:
        if os.path.isdir(f):
            continue
        base = extract_base_name(f)
        _, ext = os.path.splitext(f.lower())
        if base not in manifest:
            manifest[base] = []
        manifest[base].append({"path": f, "ext": ext})
    return manifest

def get_s3_manifest(s3_path):
    """Scans S3 bucket prefix and cleanly extracts all format variants per base dataset."""
    manifest = {}
    clean_prefix = s3_path.rstrip('/')
    try:
        all_objects = S3_FS.glob(f"{clean_prefix}/**/*")
        for obj in all_objects:
            full_s3_path = f"s3://{obj}"
            if S3_FS.isdir(obj) or full_s3_path.endswith('/'):
                continue
            if not full_s3_path.lower().endswith(('.parquet', '.pq', '.csv', '.tsv')):
                continue
            base = extract_base_name(full_s3_path)
            _, ext = os.path.splitext(full_s3_path.lower())
            if base not in manifest:
                manifest[base] = []
            manifest[base].append({"path": full_s3_path, "ext": ext})
    except Exception as e:
        print(f"❌ Error compiling S3 manifest for {s3_path}: {e}")
        return {}
    return manifest

def read_df(file_path, ext):
    """Engine to ingest dataframes safely, handling empty files and mixed dtypes."""
    try:
        if file_path.startswith("s3://"):
            clean_s3_path = file_path.replace("s3://", "")
            if 'nba_sagarin_final_ratings' in clean_s3_path or S3_FS.size(clean_s3_path) == 0:
                return pd.DataFrame()
            if ext in ['.parquet', '.pq']:
                return pd.read_parquet(file_path, filesystem=S3_FS)
            elif ext == '.csv':
                with S3_FS.open(clean_s3_path, mode='rb') as f:
                    return pd.read_csv(f, low_memory=False)
            elif ext == '.tsv':
                with S3_FS.open(clean_s3_path, mode='rb') as f:
                    return pd.read_csv(f, sep='\t', low_memory=False)
        else:
            if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                return pd.DataFrame()
            if ext in ['.parquet', '.pq']:
                return pd.read_parquet(file_path)
            elif ext == '.csv':
                return pd.read_csv(file_path, low_memory=False)
            elif ext == '.tsv':
                return pd.read_csv(file_path, sep='\t', low_memory=False)
        raise ValueError(f"Unsupported format: {ext}")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

def profile_dataset(file_path, ext):
    """Generates structural metrics along with high-fidelity quality checks on a row level."""
    df = read_df(file_path, ext)
    total_rows = len(df)
    total_cols = len(df.columns)
    col_names = list(df.columns)
    
    if total_rows == 0:
        return {
            "ext": ext,
            "col_count": 0,
            "cols": [],
            "valid_rows_count": 0,
            "valid_rows_str": "0.0%(0/0)",
            "df_cached": df
        }
    
    # 1. Base Density Condition Filters (Duplicates & High-Level Nulls)
    nan_threshold_cols = total_cols * 0.50
    is_not_duplicate = ~df.duplicated(keep=False)
    low_nan_density = df.isna().sum(axis=1) <= nan_threshold_cols
    
    # 2. Condition Filter: Drop rows where cell value string matches column header name
    is_header_leak = pd.Series(False, index=df.index)
    for col in df.columns:
        is_header_leak = is_header_leak | (df[col].astype(str).str.strip() == str(col))
        
    # 3. Condition Filter: Drop rows where TEAM and MATCH UP metrics are simultaneously empty
    team_col = next((c for c in df.columns if str(c).strip().upper() == "TEAM"), None)
    matchup_col = next((c for c in df.columns if str(c).strip().upper() in ["MATCH UP", "MATCHUP"]), None)
    
    is_empty_anchor = pd.Series(False, index=df.index)
    if team_col and matchup_col:
        team_invalid = df[team_col].isna() | (df[team_col].astype(str).str.strip() == "")
        matchup_invalid = df[matchup_col].isna() | (df[matchup_col].astype(str).str.strip() == "")
        is_empty_anchor = team_invalid & matchup_invalid
        
    # Combine conditions to verify absolute clean row records
    valid_rows_mask = is_not_duplicate & low_nan_density & (~is_header_leak) & (~is_empty_anchor)
    
    valid_rows_count = valid_rows_mask.sum()
    valid_pct = round((valid_rows_count / total_rows) * 100, 1) if total_rows > 0 else 0.0
    
    return {
        "ext": ext,
        "col_count": total_cols,
        "cols": col_names,
        "valid_rows_count": valid_rows_count,
        "valid_rows_str": f"{valid_pct}%({valid_rows_count}/{total_rows})",
        "df_cached": df[valid_rows_mask] # Only cache rows passing the quality parameters
    }

def resolve_best_internal_format(variants, base_name, loc_name):
    """Evaluates file variants inside a single source and picks the best layout."""
    best_profile = None
    best_ext = None
    best_path = None
    
    for variant in variants:
        try:
            profile = profile_dataset(variant['path'], variant['ext'])
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
                    if variant['ext'] in ['.parquet', '.pq'] and best_ext not in ['.parquet', '.pq']:
                        best_profile = profile
                        best_ext = variant['ext']
                        best_path = variant['path']
        except Exception:
            pass
            
    return best_profile, best_ext, best_path

def calculate_best_source(local_prof, s1_prof, sroot_prof):
    """Determines the best data source matching matrix strategy logic rules."""
    presence_count = sum([1 for p in [local_prof, s1_prof, sroot_prof] if p is not None])
    if presence_count <= 1 and not local_prof:
        return "-"
        
    l_count = local_prof.get("valid_rows_count", -1) if local_prof else -1
    s1_count = s1_prof.get("valid_rows_count", -1) if s1_prof else -1
    sr_count = sroot_prof.get("valid_rows_count", -1) if sroot_prof else -1
    
    max_val = max(l_count, s1_count, sr_count)
    if max_val <= 0 and l_count == s1_count == sr_count:
        return "-"
    
    if l_count == max_val:
        return "Local"
    if s1_count == sr_count and s1_count == max_val:
        return "TIE"
    if s1_count == max_val:
        return "S3_v1"
    return "S3_curation_root"

def main():
    print("=" * 100)
    print("NBA PIPELINE PRODUCTION ENGINE: DATA ARCHIVE DEPLOYMENT PHASE (v2)")
    if DRY_RUN:
        print("🚨 DRY RUN MODE ENABLED: No files will be written to S3.")
    print("=" * 100)
    
    print("-> Gathering manifests across local and remote storage arrays...")
    manifests = {
        "Local": get_local_manifest(LOCATIONS["Local"]),
        "S3_v1": get_s3_manifest(LOCATIONS["S3_v1"]),
        "S3_curation_root": get_s3_manifest(LOCATIONS["S3_curation_root"])
    }
    
    # -------------------------------------------------------------------------
    # PHASE 1: IDENTIFY AND UPLOAD LOCAL ORPHAN DATASETS TO S3 v2
    # -------------------------------------------------------------------------
    print("\nExecuting Phase 1: Tracking Local Orphan Datasets...")
    local_bases = set(manifests["Local"].keys())
    s1_bases = set(manifests["S3_v1"].keys())
    sroot_bases = set(manifests["S3_curation_root"].keys())
    
    orphan_bases = local_bases - (s1_bases | sroot_bases)
    
    if orphan_bases:
        print(f"   Found {len(orphan_bases)} local orphan bases: {list(orphan_bases)}")
        for base in sorted(orphan_bases):
            variants = manifests["Local"][base]
            profile, chosen_ext, chosen_path = resolve_best_internal_format(variants, base, "Local")
            
            if profile and not profile['df_cached'].empty:
                target_v2_url = f"{TARGET_V2_PREFIX}/{base}.parquet"
                if DRY_RUN:
                    print(f"   [DRY RUN UPLOAD] Would ingest local orphan: {base} ({len(profile['df_cached'])} clean rows) -> {target_v2_url}")
                else:
                    print(f"   [PHASE 1 UPLOAD] Ingesting local orphan: {base} -> v2 Parquet Cluster")
                    profile['df_cached'].to_parquet(target_v2_url, filesystem=S3_FS, index=False)
                    print(f"   ✅ Successfully pushed clean isolated local data to {target_v2_url}")
    else:
        print("   No orphan datasets found. Every local base exists in at least one S3 history block.")

    # -------------------------------------------------------------------------
    # PHASE 2: RECONCILE BEST SOURCES AND PUSH PURIFIED RECORDS BACK TO S3 v2
    # -------------------------------------------------------------------------
    print("\nExecuting Phase 2: Resolving Optimal Data Matrix Framework...")
    
    for base in sorted(local_bases):
        if base not in manifests["Local"]:
            print(f"   ⏩ Skipping dataset variant '{base}': Not present on Local Drive.")
            continue
            
        profiles = {}
        paths = {}
        
        for loc_name in LOCATIONS.keys():
            variants = manifests[loc_name].get(base)
            if variants:
                profile, chosen_ext, chosen_path = resolve_best_internal_format(variants, base, loc_name)
                profiles[loc_name] = profile
                paths[loc_name] = chosen_path
            else:
                profiles[loc_name] = None
                paths[loc_name] = None
                
        best_source_tag = calculate_best_source(profiles["Local"], profiles["S3_v1"], profiles["S3_curation_root"])
        print(f"\n   Reconciling [{base}] -> Optimal Selected Matrix Source Focus: **{best_source_tag}**")
        
        selected_profile = None
        
        if best_source_tag in ["Local", "-"]:
            selected_profile = profiles["Local"]
            source_log_path = paths["Local"]
        elif best_source_tag == "S3_v1":
            selected_profile = profiles["S3_v1"]
            source_log_path = paths["S3_v1"]
        elif best_source_tag == "S3_curation_root":
            selected_profile = profiles["S3_curation_root"]
            source_log_path = paths["S3_curation_root"]
        elif best_source_tag == "TIE":
            if profiles["S3_curation_root"] and not profiles["S3_curation_root"]['df_cached'].empty:
                selected_profile = profiles["S3_curation_root"]
                source_log_path = paths["S3_curation_root"]
            else:
                selected_profile = profiles["S3_v1"]
                source_log_path = paths["S3_v1"]

        if selected_profile and not selected_profile['df_cached'].empty:
            df_out = selected_profile['df_cached']
            
            # Key Column Anchor Check Protection Rules
            team_col = next((c for c in df_out.columns if str(c).strip().upper() == "TEAM"), None)
            matchup_col = next((c for c in df_out.columns if str(c).strip().upper() in ["MATCH UP", "MATCHUP"]), None)
            
            if team_col and matchup_col:
                team_valid = df_out[team_col].notna() & (df_out[team_col].astype(str).str.strip() != "")
                matchup_valid = df_out[matchup_col].notna() & (df_out[matchup_col].astype(str).str.strip() != "")
                df_out = df_out[team_valid | matchup_valid]
                
            target_v2_url = f"{TARGET_V2_PREFIX}/{base}.parquet"
            
            if DRY_RUN:
                print(f"   [DRY RUN DEPLOY] Would compile from [{source_log_path}] -> [{target_v2_url}] ({len(df_out)} filtered high-quality rows)")
            else:
                print(f"   -> Deploying optimized dataset from [{source_log_path}] -> [{target_v2_url}]")
                df_out.to_parquet(target_v2_url, filesystem=S3_FS, index=False)
                print(f"   ... Master synchronization finalized for asset block: {base}")
        else:
            print(f"   ⚠️ Warning: Dataset matrix returned an empty dataframe for: {base}. Skipping delivery.")

    print("\n" + "=" * 100)
    if DRY_RUN:
        print("✅ DRY RUN EXTRAPOLATION SUCCESSFUL: Verify outputs above before toggling DRY_RUN = False.")
    else:
        print("✅ PIPELINE EXECUTION SUMMARY SUCCESSFUL: TARGET STORAGE LAYER v2 SYNC COMPLETED")
    print("=" * 100)

if __name__ == '__main__':
    main()