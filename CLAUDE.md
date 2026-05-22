THis repo (/nba) is the system for building and automating trades for nba on kalshi bets. It follows de Prado's framework using the following steps.. All packages are in the conda environment 'pred'

1. data curator
data is curated from nba and espn for now, and will be expanded as needed
the current data needed includes crowd density (audience count over venue capacity), box score data, game location, and roster. For example, at the current phase, we should be getting audience density from the following endpoints:

https://sports.core.api.espn.com/v2/{season}/types/{type}/teams/{team}/attendance

ESPN also documents per-game attendance and venue capacity in its response schemas, which means you can compute a density proxy like attendance / capacity:

scoreboard schema includes attendance and venue capacity in [response_schemas.md](/Users/michaelharoon/Projects/Prediction markets/nba/api_docs/espn_api_docs/docs/response_schemas.md:52)

And possible predictive rating (power or BPI) from ESPN: So ESPN definitely exposes a predictive rating surface in basketball, but the documented example is college BPI, not a dedicated NBA BPI standings/rating endpoint.

For NBA specifically, the strongest documented predictive signal is in game summaries. In response_schemas.md (line 326), the summary?event={id} response includes a predictor object with:


header: "ESPN BPI Win Probability"

homeTeam.gameProjection

homeTeam.teamChanceLoss.

2. feature analysis
features are engineered to mimic the following:
    diff_massey_SAG
    diff_massey_POM
    diff_massey_WLK
    diff_seed_num
    diff_massey_DOL
    diff_massey_PMW
    diff_consensus_rank
    diff_massey_MOR
    diff_massey_RPI
    diff_massey_COL
    diff_kg_scoring_margin
    diff_kg_wins
    diff_kg_margin_last10_delta
    diff_kg_win_pct
    diff_massey_BPI
    diff_kg_losses
    diff_path_best_opp_seed
    diff_kg_net_strong_margin
    diff_path_games_played

there are playoff specific features as you can note. Such features are only important during playoffs

In this step, we need to of course run mdi, mda, and sfi on features, clustering them when needed, and most importantly we need to run pca cross checking to derive orthogonal features using principal component analysis (unsupervised) so that if the features PCA identifies as "principal" (structural) match those identified as "important" (predictive) by MDI/MDA/SFI, it provides confirmatory evidence that the pattern is not overfit. Our sanity check will be in the final training where we compare cal loss to training loss. And of course, Compute a weighted Kendall’s tau between the supervised importance ranks and the unsupervised PCA ranks. A value close to 1 justifies the selection of those features.

This step is key! It determines everything.

3. strategy
this step yields our trading strategy. We must choose the right model. we make a model that spits an output like the probability of a team winning given its data, then from there we need to account for risk, confidence interval of model, kalshi's api (eg. speed and basic infra), and accuracy of our bets to learn from it

4. Backtesting
this step evaluates probability of backtest overfitting

5. Oversight
the life cycle is to test on out of sample data, paper trade, re-allocation based on performance, decommission when theory ends.



CRITICAL: DATA LEAKAGE PREVENTION
___
All features used for prediction MUST come from BEFORE the game date. Never use same-game or post-game data as features.
- Temporal embargo: ratings/stats from day T can only predict games on day T+1 or later
- Purging: cross-validation folds must be purged so that no training data overlaps temporally with test data (PurgedYearKFold handles this)
- Same-game box scores (pts, fgm, offrtg, etc.) are OUTCOMES, not features. Only rolling averages of PRIOR games are valid features.
- When in doubt, ask: "could I know this value BEFORE tipoff?" If no, it's leakage.

Short comings of this approach
___
This is a frequentist approach that might lack the power at the start of a season since rosters might have changed.

---
Always make sure the CLAUDE.md (this file) is always up to date. Also, be sure to add a list of added/engineered features to FEATURES.md
---
team_mappings.parquet is the best maping we have between espn and nba right now