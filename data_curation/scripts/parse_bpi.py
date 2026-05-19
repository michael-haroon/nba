import json
import pandas as pd
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================
SOURCE_DIR = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data/output/espn_bpi_wayback")
OUTPUT_FILE = Path("/Users/michaelharoon/Projects/Prediction markets/nba/data/output/nba_bpi_timeseries.parquet")

def extract_all_stats(data, results=None):
    if results is None: results = []
    if isinstance(data, list):
        for item in data: extract_all_stats(item, results)
    elif isinstance(data, dict):
        if 'team' in data and 'stats' in data:
            results.append(data)
        for value in data.values():
            extract_all_stats(value, results)
    return results

def build_parquet():
    files = sorted(list(SOURCE_DIR.glob("*.html")))
    all_rows = []

    print(f"Processing {len(files)} files into Parquet...")

    for f_path in files:
        timestamp = f_path.stem.split('_')[-1]
        content = f_path.read_text(encoding='utf-8', errors='ignore')
        
        json_str = ""
        for marker in ["window['__espnfitt__']=", "window['__CONFIG__']="]:
            if marker in content:
                json_str = content.split(marker)[1].split(';</script>')[0]
                break
        
        if not json_str:
            continue

        try:
            data = json.loads(json_str)
            team_entries = extract_all_stats(data)
            
            for entry in team_entries:
                row = {
                    "snapshot_timestamp": timestamp,
                    "team_id": entry['team'].get('id'),
                    "team_name": entry['team'].get('displayName'),
                    "team_abbrev": entry['team'].get('abbrev')
                }
                
                for s in entry.get('stats', []):
                    stat_name = s.get('name')
                    stat_val = s.get('value')
                    
                    if stat_name:
                        # CLEANING STEP: Handle ESPN's empty placeholder '--'
                        if stat_val == '--':
                            row[stat_name] = None
                        else:
                            try:
                                row[stat_name] = float(stat_val)
                            except (ValueError, TypeError):
                                row[stat_name] = stat_val
                
                all_rows.append(row)
                
        except Exception as e:
            print(f"Error processing {timestamp}: {e}")

    df = pd.DataFrame(all_rows)

    # Final Safety Check: Force numeric conversion for known float columns
    # This turns any straggling strings into NaN
    float_cols = ['bpi', 'off', 'def', 'sos', 'sor', 'playoffbpi', 'offtalent', 'deftalent']
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df['snapshot_timestamp'] = pd.to_datetime(df['snapshot_timestamp'], format='%Y%m%d%H%M%S')

    # Save to Parquet
    df.to_parquet(OUTPUT_FILE, index=False, compression='snappy')
    
    print("\n" + "="*30)
    print(f"SUCCESS: {OUTPUT_FILE.name} created.")
    print(f"Total Rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print("="*30)

if __name__ == "__main__":
    build_parquet()