# Engineered Features

## Rating Features (temporally aligned — rating from day T used only for games on T+1+)
- `diff_bpi` — ESPN Basketball Power Index
- `diff_bpioffense`, `diff_bpidefense` — BPI offensive/defensive components
- `diff_playoffbpi` — BPI playoff variant
- `diff_offtalent`, `diff_deftalent` — ESPN talent ratings
- `diff_sag_rating` — Sagarin composite rating
- `diff_elo_score` — Sagarin Elo variant
- `diff_predictor` — Sagarin predictor rating
- `diff_pure_elo` — Sagarin pure Elo
- `diff_golden_mean` — Sagarin golden mean
- `diff_recent` — Sagarin recency-weighted rating

## Massey Rating Features (fitted pregame, no lookahead)
- `diff_default_massey` — base Massey system (X @ beta = y)
- `diff_location_adjusted_massey` — home advantage factor
- `diff_crowd_adjusted_massey` — crowd density factor
- `diff_crowd_weighted_massey` — game-weighted by crowd
- `diff_experience_adjusted_massey` — visitor inexperience factor
- `diff_travel_adjusted_massey` — travel distance + direction
- `diff_context_adjusted_massey` — all contextual factors combined

## Rolling Box Score Features (windows: 5, 10, 20 games)
Per window N, for each stat: `diff_roll{N}_{stat}` and `diff_roll{N}_{stat}_std`

Stats include:
- pts, fgm, fga, fgpct, 3pm, 3pa, 3ppct, ftm, fta, ftpct
- oreb, dreb, reb, ast, tov, stl, blk, pf, plus_minus
- offrtg, defrtg, netrtg, astpct, ast_to, ast_ratio
- orebpct, drebpct, rebpct, tovpct, efgpct, tspct, pace, pie
- fta_rate, opp_efgpct, opp_fta_rate, opp_tovpct, opp_orebpct
- pts_off_to, 2nd_pts, fbps, pitp, opp_pts_off_to, opp_2nd_pts, opp_fbps, opp_pitp
- pctfga_2pt, pctfga_3pt, pctpts_2pt, pctpts_3pt, pctpts_ft, fgm_pctast, fgm_pctuast

## Momentum Features
- `diff_win_streak` — consecutive wins (rolling 20)
- `diff_margin_last1`, `diff_margin_last3`, `diff_margin_last5` — recent scoring margins
- `diff_win_pct_20` — rolling 20-game win percentage
- `diff_win_entropy` — Shannon entropy of recent W/L sequence (de Prado)
- `diff_cusum_momentum` — CUSUM momentum shift detection (de Prado)

## Context & Travel Features
- `diff_days_rest` — days since last game
- `diff_is_back_to_back` — played yesterday (binary)
- `away_travel_distance` — haversine miles from away team's arena to game
- `away_timezone_shift` — timezone hours gained/lost by away team
- `crowd_density` — attendance / venue capacity
- `sellout_flag` — binary

## Referee Features
- `crew_home_win_rate` — historical home win rate of referee crew
- `crew_avg_total` — historical avg total points with this crew
- `crew_experience` — avg games officiated by crew

## Roster Features
- `diff_active_players` — active roster size difference
- `diff_dnp_count` — DNP count difference

## Series Features (playoffs only)
- `series_game_number` — which game in the series (1-7)
- `series_lead` — entering series wins advantage

## Random Weighted Combinations (de Prado approach)
- `rc_000` through `rc_049` — 50 random linear combinations of diff features
- Configurable via N_RANDOM_COMBOS env var (scale to 500+ on GPU instances)
- Fixed seed=42 for reproducibility; weight vectors stored deterministically

## Feature Selection Method
Features are filtered via de Prado's importance framework:
1. ONC clustering (optimal number of clusters on correlation matrix)
2. MDI (Mean Decrease Impurity) — in-sample importance
3. MDA (Mean Decrease Accuracy) — out-of-sample via purged CV
4. SFI (Single Feature Importance) — immune to substitution effects
5. PCA cross-check — weighted Kendall's tau between PCA ranks and importance ranks
6. Survivors must pass STRONG or MODERATE tier in at least 2 of MDI/MDA/SFI
