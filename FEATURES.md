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
- `diff_colley` — Colley rating: r_i = (1+w_i)/(2+t_i) with SOS via C=2I+M

## Per-Quarter Massey & Colley Ratings (fitted pregame, no lookahead)
For each quarter Q (q1–q4), the same 7 Massey designs + Colley are fit using
quarter-specific point differentials as targets. Captures which teams dominate
specific periods — e.g., fast starters (Q1) vs closers (Q4).

- `diff_{design}_q{N}` — Massey rating fitted on quarter N margins only
- `diff_colley_q{N}` — Colley rating using per-quarter W/L (outscore = win)

All 7 Massey designs are computed per quarter:
  default, location_adjusted, crowd_adjusted, crowd_weighted,
  experience_adjusted, travel_adjusted, context_adjusted

Total: 32 features (8 systems × 4 quarters)

Hypothesis: home-court effects (crowd, travel) are non-uniform across quarters.
Crowd is loudest at tip-off and crunch time; jet lag may hit early (Q1) or late (Q4).
The filter pipeline decides what survives.

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

## Venue-Conditioned Rolling Features (home/road performance splits)
Per window N (10, 20), for key efficiency stats:
`diff_roll{N}_{stat}_venue` = home team's rolling avg AT HOME − away team's rolling avg ON ROAD

Stats: pts, offrtg, defrtg, netrtg, pace, efgpct

This isolates location-specific performance — a team that shoots 48% eFG at home
but 44% on the road will show a clear signal here that blended rolling stats mask.

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

## Travel Sequence & Fatigue Features
Captures cumulative travel burden over recent games. Key insight: 5 away games
in 5 days across the country is far worse than 5 away games in 10 days nearby.

- `diff_away_streak` — consecutive away games entering this game
- `diff_days_span_{3,5}` — calendar days spanned by last N games (schedule density)
- `diff_games_per_week_{3,5}` — games per 7 days over last N games (compression)
- `diff_venue_switches_{3,5}` — home/away flips in last N games (H-A-H-A disruption)
- `diff_travel_distance_{3,5}` — cumulative game-to-game miles over last N games
- `diff_travel_intensity_{3,5}` — travel_distance / days_span (miles per day; captures
  far games packed tight vs spread out)

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

## Sum Features (complement to diffs — predict total-type targets)
For every home_X / away_X pair: `sum_X = home_X + away_X`

Diffs predict WHO wins; sums predict HOW MUCH scoring happens.
- `sum_massey` — combined team quality (high + close diff = tight elite matchup)
- `sum_roll{N}_pace` — combined pace (predicts total)
- `sum_roll{N}_offrtg` — combined offensive output
- `sum_win_streak` — combined momentum (two hot teams = competitive)
- All ~564 sum features generated (same columns as diffs)

## Pythagorean Expectation & Residual
- `diff_pyth_exp_winpct` — Morey formula: PF^13.91 / (PF^13.91 + PA^13.91)
- `diff_pyth_residual` — actual_win% - expected_win% (mean-reversion signal)

## Log5 Implied Probability
- `log5_implied_prob` — P(home>away) = (pA - pA*pB) / (pA + pB - 2*pA*pB)
- Bradley-Terry equivalent using rolling 20-game win percentages

## Four Factors Composite
- `diff_ff_composite` — eFG% × (1 - TOV%) [conditional shooting quality]
- `diff_ff_oliver_index` — 0.4*eFG% + 0.25*(1-TOV%) + 0.2*ORB% + 0.15*FTRate

## Pace Mismatch
- `pace_mismatch` — |home_pace - away_pace| (disruption signal)
- `combined_pace` — (home_pace + away_pace) / 2 (total predictor)

## Scoring Distribution Entropy
- `diff_scoring_entropy` — H = -Σ(p_i × log2(p_i)) over scoring source proportions
- Higher entropy = more balanced/diverse scoring = harder to defend

## ACWR (Acute:Chronic Workload Ratio)
- `diff_acwr_pts` — EWMA ratio (λ_acute=0.25, λ_chronic=0.069) on points
- `diff_acwr_netrtg` — same applied to net rating
- `diff_acwr_risk` — binary flag: ACWR outside [0.80, 1.30] sweet spot

## Directional Travel
- `away_eastward_hours` — hours of eastward timezone shift
- `away_directional_fatigue` — east_hours × 1.5 + west_hours × 1.0 (asymmetric)

## Quarter Rolling Stats (critical for half targets)
- `diff_roll10_q{1-4}` — rolling 10-game mean of quarter scoring per team
- `diff_roll10_h1_pts` — Q1 + Q2 rolling (predicts h1_spread, h1_total)
- `diff_roll10_h2_pts` — Q3 + Q4 rolling (predicts h2_spread, h2_total)

## Blowout & Close Game Rates
- `diff_blowout_rate_10` — fraction of last 10 games with |margin| > 15
- `diff_close_game_rate_10` — fraction of last 10 with |margin| ≤ 5 (OT signal)

## Overtime History
- `diff_ot_frequency` — fraction of last 20 games going to OT
- `diff_ot_win_rate` — expanding OT win rate within season

## Margin Autocorrelation
- `diff_margin_autocorr` — lag-1 autocorrelation over rolling 20-game window
- Positive = momentum; Negative = mean-reversion

## Defensive Consistency
- `diff_def_consistency` — DefRtg mean / DefRtg std (coefficient of variation)
- High ratio = reliable defense (low variance relative to level)

## Scoring Concentration (Gini/Herfindahl)
- `diff_scoring_gini` — 1 - Σ(p_i²) [Simpson diversity of scoring sources]

## Series-Specific Features (playoffs only)
- `higher_seed_flag` — derived from home court in game 1
- `series_rest_days` — days since last game in this series pair
- `series_home_win_rate` — home win rate within the current series

## Team Hustle Aggregates (from HustlePlayerStats)
- `diff_deflections_10` — rolling 10-game team deflections
- `diff_contestedshots_10` — rolling 10-game contested shots
- `diff_looseballsrecoveredtotal_10` — rolling loose balls recovered
- `diff_screenassists_10` — rolling screen assists

## Half Scoring Rate
- `diff_h1_scoring_rate` — first half pts / total pts ratio
- `diff_h2_scoring_rate` — second half pts / total pts ratio

## Random Symbolic Features (replaces old linear random combinations)
- `sf_000` through `sf_499` — 500 randomly generated symbolic features
- Grammar: 2-3 inputs from diff_* + sum_* pool, operations: multiply, divide, add, subtract
- Unary transforms (P=0.3): abs, square, log1p, sqrt
- Ternary operations: a*b+c, a*b*c, a/(b+c)
- Each recipe saved to `symbolic_recipes.json` for post-hoc interpretation of survivors
- Configurable via N_SYMBOLIC_FEATURES env var (default: 500)
- Fixed seed=42 for reproducibility

## Adaptive Huber Delta CV (strategy layer)
For regression targets, the Huber loss delta is now selected per-fold via nested CV:
- Grid: [0.5, 0.75, 1.0, 1.25, 1.5] × MAD/0.6745 (robust sigma estimate)
- Inner 3-fold time-based CV minimizes MAE
- Target-specific and era-adaptive (each outer fold gets its own delta)

## Feature Selection Method
Features are filtered via de Prado's importance framework:
1. ONC clustering (optimal number of clusters on correlation matrix)
2. MDI (Mean Decrease Impurity) — in-sample importance
3. MDA (Mean Decrease Accuracy) — out-of-sample via purged CV
4. SFI (Single Feature Importance) — immune to substitution effects
5. PCA cross-check — weighted Kendall's tau between PCA ranks and importance ranks
6. Survivors must pass STRONG or MODERATE tier in at least 2 of MDI/MDA/SFI
