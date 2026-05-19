import re
import pandas as pd
from pathlib import Path

def parse_sagarin_strict(file_path):
    with open(file_path, 'r', encoding='latin-1') as f:
        content = f.read()

    # 1. Identify the Season/Date (The very first specific line)
    date_match = re.search(r"NBA \d{4}-\d{4} through .*? of (.*)", content)
    date_str = date_match.group(1).strip() if date_match else "Unknown"

    # 2. Identify Column Structure (Look for the RATING block)
    # We find which specialty ratings exist (PREDICTOR, ELO_SCORE, etc.)
    header_block = re.search(r"RATING\n.*?VS top 16 \|\n(.*?)\n\nHOME ADVANTAGE", content, re.DOTALL)
    if header_block:
        col_names = re.findall(r"PREDICTOR|ELO_SCORE|GOLDEN_MEAN|RECENT|BLUE|COMBO|PURE_ELO", header_block.group(1))
    else:
        col_names = ["PREDICTOR"] # Fallback

    # 3. Capture Home Advantage values
    home_adv_match = re.search(r"HOME ADVANTAGE=\[(.*?)\]", content)
    home_val = home_adv_match.group(1).strip() if home_adv_match else "3.00"

    # 4. Parse Team Blocks
    # We split by Rank + Team + "=" and then look at the text immediately following it
    teams = []
    # Pattern looks for: Start of line, Digits (Rank), Name, then "="
    team_regex = re.compile(r"^\s*(\d+)\s+(.*?)\s+=", re.MULTILINE)
    
    matches = list(team_regex.finditer(content))
    for i, match in enumerate(matches):
        rank = match.group(1)
        name = match.group(2).strip()
        
        # Skip Division rows
        if name.isupper() and len(name.split()) <= 2:
            if not any(x in name for x in ["HEAT", "JAZZ", "MAGIC", "SUNS", "NETS", "KINGS"]):
                continue

        # The data for this team starts after the "=" and ends before the next team starts
        start_pos = match.end()
        end_pos = matches[i+1].start() if i+1 < len(matches) else len(content)
        data_block = content[start_pos:end_pos]

        # First number after the "=" is always the Overall Rating
        overall_rating_match = re.search(r"(\d+\.\d+)", data_block)
        overall_rating = overall_rating_match.group(1) if overall_rating_match else "0.00"

        # Specialized ratings are the numbers found inside the vertical pipes |
        # In your example: | 100.20 1 | 99.46 1 | 98.60 1
        pipe_values = re.findall(r"\|\s*(\d+\.\d+)", data_block)
        
        # Map found pipe values to our identified column headers
        row = {
            "date": date_str,
            "rank": int(rank),
            "team": name,
            "overall_rating": float(overall_rating),
            "home_advantage": float(home_val)
        }
        
        for idx, col in enumerate(col_names):
            if idx < len(pipe_values):
                row[col.lower()] = float(pipe_values[idx])

        teams.append(row)

    return teams

# Batch execution
input_dir = Path("data_curation/data/unscraped_sites/usatoday_sag/cleaned_ratings")
all_data = []
for f in input_dir.glob("*.txt"):
    all_data.extend(parse_sagarin_strict(f))

df = pd.DataFrame(all_data)
df.to_csv("nba_historical_clean.csv", index=False)