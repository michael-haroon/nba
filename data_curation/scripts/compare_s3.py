import os
import glob
import re
import sys
import logging
import traceback
import contextlib
import pandas as pd
import boto3
from s3fs import S3FileSystem

# --- CONFIGURATION ---
LOCATIONS = {
    "Local": "/Users/michaelharoon/Projects/prediction_markets/nba/data_curation/data",
    "S3_v1": "s3://nba-265753586044-us-east-1-an/data/v1",
    "S3_curation_root": "s3://nba-265753586044-us-east-1-an/nba/data_curation/data"
}

LOG_FILE_PATH = "compare_s3_audit.log"

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
        print(f"❌ Error compiling S3 manifest for {s3_path}:")
        traceback.print_exc()
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
            "valid_rows_str": "0.0%(0/0)"
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
        "valid_rows_str": f"{valid_pct}%({valid_rows_count}/{total_rows})"
    }

def resolve_best_internal_format(variants, base_name, loc_name):
    """
    Evaluates file variants inside a single source. Profiles all available
    extensions, selects the layout with the maximum high-quality row count, 
    and breaks ties by prioritizing Parquet formats.
    """
    best_profile = None
    best_ext = None
    
    for variant in variants:
        try:
            profile = profile_dataset(variant['path'], variant['ext'])
            if best_profile is None:
                best_profile = profile
                best_ext = variant['ext']
            else:
                current_max = best_profile['valid_rows_count']
                candidate_val = profile['valid_rows_count']
                
                if candidate_val > current_max:
                    best_profile = profile
                    best_ext = variant['ext']
                elif candidate_val == current_max:
                    if variant['ext'] in ['.parquet', '.pq'] and best_ext not in ['.parquet', '.pq']:
                        best_profile = profile
                        best_ext = variant['ext']
        except Exception as e:
            print(f"\n⚠️ CRITICAL READ FAILURE: [{base_name}] format variant [{variant['ext']}] in [{loc_name}]")
            traceback.print_exc()
            
    return best_profile, best_ext

def calculate_best_source(local_prof, s1_prof, sroot_prof):
    """
    Determines the best data source using strict priority conditions.
    Returns 'TIE' if both S3 layers equal or exceed local quality thresholds.
    """
    presence_count = sum([1 for p in [local_prof, s1_prof, sroot_prof] if p is not None])
    
    if presence_count <= 1:
        return "-"
        
    l_count = local_prof.get("valid_rows_count", -1) if local_prof else -1
    s1_count = s1_prof.get("valid_rows_count", -1) if s1_prof else -1
    sr_count = sroot_prof.get("valid_rows_count", -1) if sroot_prof else -1
    
    max_val = max(l_count, s1_count, sr_count)
    if max_val <= 0 and l_count == s1_count == sr_count:
        return "-"
    
    # --- EVALUATE EXPLICIT S3 TIE CONDITION ---
    if l_count == max_val:
        return "Local"
    
    if s1_count == sr_count and s1_count == max_val:
        return "TIE"
    if s1_count == max_val:
        return "S3_v1"
    return "S3_curation_root"

def run_multi_reconciliation():
    print("Gathering metadata profiles across environments...")
    
    manifests = {
        "Local": get_local_manifest(LOCATIONS["Local"]),
        "S3_v1": get_s3_manifest(LOCATIONS["S3_v1"]),
        "S3_curation_root": get_s3_manifest(LOCATIONS["S3_curation_root"])
    }
    
    all_bases = set()
    for loc_name, manifest in manifests.items():
        all_bases.update(manifest.keys())
        print(f" -> Found {len(manifest)} unique dataset bases in [{loc_name}]")
        
    comparison_records = []
    
    for base in sorted(all_bases):
        record = {"Dataset (Base)": base}
        profiles = {}
        
        for loc_name, manifest in manifests.items():
            variants = manifest.get(base)
            if variants:
                profile, chosen_ext = resolve_best_internal_format(variants, base, loc_name)
                if profile:
                    profiles[loc_name] = profile
                    record[f"{loc_name} (Ext)"] = chosen_ext
                    record[f"{loc_name} (Cols Count)"] = profile['col_count']
                    record[f"{loc_name} (Valid Row Quality)"] = profile['valid_rows_str']
                else:
                    profiles[loc_name] = None
                    record[f"{loc_name} (Ext)"] = "ERR"
                    record[f"{loc_name} (Cols Count)"] = "ERR"
                    record[f"{loc_name} (Valid Row Quality)"] = "ERR"
            else:
                profiles[loc_name] = None
                record[f"{loc_name} (Ext)"] = "-"
                record[f"{loc_name} (Cols Count)"] = "-"
                record[f"{loc_name} (Valid Row Quality)"] = "-"
                
        # --- COMPUTE INTER-COLUMN SCHEMA DISCREPANCIES ---
        local_cols = profiles["Local"]['cols'] if (profiles["Local"] and isinstance(profiles["Local"], dict)) else None
        
        for loc_name in ["S3_v1", "S3_curation_root"]:
            p = profiles[loc_name]
            if record[f"{loc_name} (Cols Count)"] in ["-", "ERR"]:
                record[f"{loc_name} (Schema Diff)"] = record[f"{loc_name} (Cols Count)"]
            elif local_cols is None:
                record[f"{loc_name} (Schema Diff)"] = "No Local Baseline"
            else:
                rem_cols = p['cols']
                diff_added = set(rem_cols) - set(local_cols)
                diff_dropped = set(local_cols) - set(rem_cols)
                
                if not diff_added and not diff_dropped:
                    if local_cols == rem_cols:
                        record[f"{loc_name} (Schema Diff)"] = "Match"
                    else:
                        record[f"{loc_name} (Schema Diff)"] = "Order Discrepancy"
                else:
                    msg_pieces = []
                    if diff_added: msg_pieces.append(f"+{list(diff_added)}")
                    if diff_dropped: msg_pieces.append(f"-{list(diff_dropped)}")
                    record[f"{loc_name} (Schema Diff)"] = " / ".join(msg_pieces)

        record["Local (Schema Diff)"] = "Baseline" if local_cols is not None else "-"
        
        # --- COMPUTE OPTIMAL HIGH-QUALITY DATA SOURCE ---
        record["Best Source"] = calculate_best_source(profiles["Local"], profiles["S3_v1"], profiles["S3_curation_root"])

        # --- ALERTS & DISCREPANCY SELECTION ---
        is_different = (
            record["Local (Ext)"] == "-" or
            record["S3_v1 (Ext)"] == "-" or
            record["S3_curation_root (Ext)"] == "-" or
            record["Local (Cols Count)"] != record["S3_v1 (Cols Count)"] or
            record["Local (Cols Count)"] != record["S3_curation_root (Cols Count)"] or
            record["S3_v1 (Schema Diff)"] not in ["Match", "-"] or
            record["S3_curation_root (Schema Diff)"] not in ["Match", "-"] or
            record["Local (Valid Row Quality)"] != record["S3_v1 (Valid Row Quality)"] or
            record["Local (Valid Row Quality)"] != record["S3_curation_root (Valid Row Quality)"]
        )
        
        if is_different:
            record["Dataset (Base)"] = f"🚨 {base}"
        else:
            record["Dataset (Base)"] = f"✅ {base}"
            
        comparison_records.append(record)

    df_master = pd.DataFrame(comparison_records)

    # --- WRITING RESULTS OUT TO DISK LOG FILE ---
    with open(LOG_FILE_PATH, "w", encoding="utf-8") as f_log:
        with contextlib.redirect_stdout(f_log):
            print("="*120)
            print("Cross-Environment Audit Matrix (✅ indicates clean matches with Local baseline across all layers)")
            print("="*120)
            
            print("\n### 1. File Availability & Format Version Selected Matrix")
            ext_cols = ["Dataset (Base)"] + [f"{loc} (Ext)" for loc in LOCATIONS.keys()]
            print(df_master[ext_cols].set_index("Dataset (Base)").to_markdown())
            
            print("\n### 2. Schema Integrity Matrix (Column Counts & Data Variances)")
            col_metric_headers = ["Dataset (Base)"]
            for loc in LOCATIONS.keys():
                col_metric_headers.extend([f"{loc} (Cols Count)", f"{loc} (Schema Diff)"])
            print(df_master[col_metric_headers].set_index("Dataset (Base)").to_markdown())

            print("\n### 3. High-Quality Rows Matrix & Data Selection")
            qual_cols = ["Dataset (Base)"] + [f"{loc} (Valid Row Quality)" for loc in LOCATIONS.keys()] + ["Best Source"]
            print(df_master[qual_cols].set_index("Dataset (Base)").to_markdown())

    print(f"\n✅ Processing complete. Matrix tables written cleanly to: '{LOG_FILE_PATH}'")
    
    # --- REDESIGNED RAW TERMINAL PRINT GRID ---
    print("\n" + "="*120)
    print("TERMINAL AUDIT MATRIX PREVIEW (Full details recorded in log file)")
    print("="*120)
    
    preview_cols = [
        "Dataset (Base)",
        "Local (Ext)", "Local (Valid Row Quality)", 
        "S3_v1 (Ext)", "S3_v1 (Valid Row Quality)", 
        "S3_curation_root (Ext)", "S3_curation_root (Valid Row Quality)", 
        "Best Source"
    ]
    
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_columns', None)
    print(df_master[preview_cols].set_index("Dataset (Base)").to_string())

if __name__ == '__main__':
    run_multi_reconciliation()