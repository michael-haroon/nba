import pandas as pd
import re
import numpy as np

def get_structural_fingerprint(row_val):
    """
    Counts how many numeric groups exist after the '=' sign.
    Helps distinguish between 2015 layout and 2021 layout.
    """
    if pd.isna(row_val) or '=' not in str(row_val):
        return 0
    after_equals = str(row_val).split('=')[1]
    return len(re.findall(r"[-+]?\d*\.\d+|\d+", after_equals))

def clean_sag_data(df, rating_col, date_col='date', team_col='team'):
    df = df.copy()
    
    # 1. Parse Date
    def extract_date(s):
        match = re.search(r'(\d{4}\s+[a-zA-Z]+\s+\d{1,2})', str(s))
        return match.group(1) if match else None
    df['parsed_date'] = pd.to_datetime(df[date_col].apply(extract_date), format='%Y %B %d', errors='coerce')
    
    # 2. Structural Guardrail: Filter by 'Sanity'
    # Force ratings and ranks to numeric early
    df['rank'] = pd.to_numeric(df['rank'], errors='coerce')
    df[rating_col] = pd.to_numeric(df[rating_col], errors='coerce')

    # FIX: Remove "Hallucinated" ratings. 
    # NBA ratings in Sagarin are never 9354 or 0.5. They stay between 60 and 110.
    df = df[(df[rating_col] > 60) & (df[rating_col] < 110)]
    
    # 3. Enhanced Keyword Filtering
    non_team_keywords = [
        'NORTHWEST', 'SOUTHWEST', 'PACIFIC', 'SOUTHEAST', 'CENTRAL', 'ATLANTIC', 
        'WEST', 'EAST', 'CONFERENCE', 'DIVISION', 'NBA', 'RANK', 'RATING', 'AVERAGE'
    ]
    
    # Strictly enforce team name quality
    def is_real_team(name):
        n = str(name).upper()
        if any(kw in n for kw in non_team_keywords): return False
        if len(n.strip()) < 3: return False 
        return True

    df = df[df[team_col].apply(is_real_team)]
    
    # 4. Remove NaNs and DEDUPLICATE
    # Important: Drop based on 'rank' to ensure we only have actual ranked lines
    df = df.dropna(subset=['parsed_date', 'rank', rating_col])
    
    # Sort by date and rating to keep the most 'reasonable' entry if duplicates exist
    df = df.sort_values(['parsed_date', 'team', rating_col], ascending=[True, True, False])
    df = df.drop_duplicates(subset=['parsed_date', 'team'], keep='first')
    
    return df

def generate_audit():
    # ... (Paths and Header Setup stay the same) ...
    base_path = "/Users/michaelharoon/Projects/Prediction markets/nba/data_curation/data/"
    hist_file = base_path + "sag_nba_historical_clean.csv"
    mast_file = base_path + "sag_nba_master_ratings.csv"
    hist_cols = ['date','rank','team','overall_rating','home_advantage','golden_mean','predictor','pure_elo','recent','elo_score']
    mast_cols = ['date','rank','team','rating','predictor','home_edge']

    # Load with low_memory=False
    df_hist = pd.read_csv(hist_file, names=hist_cols, low_memory=False)
    df_mast = pd.read_csv(mast_file, names=mast_cols, low_memory=False)

    # Calculate Fingerprints on raw data BEFORE cleaning
    # This helps diagnose why the Hawks (93.54) issue happened
    df_mast['fingerprint'] = df_mast['date'].apply(get_structural_fingerprint)

    # Clean
    df_h = clean_sag_data(df_hist, 'overall_rating')
    df_m = clean_sag_data(df_mast, 'rating')

    # 1. Date Metrics Helper
    def get_date_metrics(df, prefix):
        # We group by date to see if the whole DAY is suspicious
        m = df.groupby('parsed_date').agg(
            team_count=('team', 'count'),
            max_rank=('rank', 'max'),
            avg_rating=(df.columns[df.columns.isin(['overall_rating', 'rating'])][0], 'mean')
        ).reset_index()
        
        m['is_monotonic'] = df.groupby('parsed_date')['rank'].apply(
            lambda x: sorted(x.unique().tolist()) == list(range(1, len(x) + 1))
        ).values
        
        return m.rename(columns={
            'team_count': f'team_count_{prefix}',
            'max_rank': f'max_rank_{prefix}',
            'is_monotonic': f'is_monotonic_{prefix}',
            'avg_rating': f'avg_rating_{prefix}'
        })

    h_metrics = get_date_metrics(df_h, 'hist')
    m_metrics = get_date_metrics(df_m, 'mast')

    # 2. Merging
    audit = pd.merge(
        df_h[['parsed_date', 'team', 'rank', 'overall_rating']],
        df_m[['parsed_date', 'team', 'rank', 'rating']],
        on=['parsed_date', 'team'],
        how='outer',
        suffixes=('_hist', '_mast')
    )

    audit = pd.merge(audit, h_metrics, on='parsed_date', how='left')
    audit = pd.merge(audit, m_metrics, on='parsed_date', how='left')

    # 3. New Logic: Flagging "Structural Drift"
    audit['rating_diff'] = (audit['overall_rating'] - audit['rating']).abs()
    audit['rank_diff'] = (audit['rank_hist'] - audit['rank_mast']).abs()

    conditions = [
        (audit['rating_diff'] > 0.5), # Tighter tolerance for rating
        (audit['rank_diff'] > 0),
        (audit['overall_rating'].isna() | audit['rating'].isna()),
        (audit['team_count_hist'] < 28) | (audit['team_count_hist'] > 31),
        (audit['is_monotonic_hist'] == False),
        ((audit['overall_rating'] < 65) | (audit['overall_rating'] > 105)) # Hard sanity bounds
    ]
    choices = ["RATING_DRIFT", "RANK_MISMATCH", "MISSING_DATA", "BAD_COUNT", "RANK_GAPS", "OUTLIER_VALUE"]
    
    audit['issue_flag'] = ""
    for cond, label in zip(conditions, choices):
        audit.loc[cond, 'issue_flag'] += label + "|"

    # Final Save
    output_path = base_path + "sag_audit_report.csv"
    audit.to_csv(output_path, index=False)
    print(f"Audit completed. Review {output_path}")

if __name__ == "__main__":
    generate_audit()