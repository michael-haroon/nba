- [?] add NOK to the mapping and curated history

- Add the following data:
    - [X] AdvBoxScoresTradPre
    - [X] AdvBoxScoresTradRegular
    - [X] AdvBoxScoresTradPlayoffs
    - [X] AdvBoxScoresAdvPre
    - [X] AdvBoxScoresAdvRegular
    - [X] AdvBoxScoresAdvPlayoffs
    - [X] AdvBoxScoresFourFactorsPre
    - [X] AdvBoxScoresFourFactorsRegular
    - [X] AdvBoxScoresFourFactorsPlayoffs
    - [X] AdvBoxScoresMiscPre
    - [X] AdvBoxScoresMiscRegular
    - [X] AdvBoxScoresMiscPlayoffs
    - [X] AdvBoxScoresScoringPre
    - [X] AdvBoxScoresScoringRegular
    - [X] AdvBoxScoresScoringPlayoffs
    - [ ] GeneralAdv (for possessions)
    - [X] Hustle endpoint
    - [X] BoxScoreSummary endpoint

- We need to be able to download Massey ratings from his website on aws using selenium or chrome
- We need more SAG and BPI data

- [ ] We need to analyze features for the OVERTIME target



🔴🔴🔴 Most importantly, learn more about the industry and its players 
🔴🔴🔴 CROSS MARKET PRICING WITHIN AN EXCHANGE IS OFTEN WRONG! For example, think of NCAA. it shows 4 differnet probability for seires but then 50/50 for mich and ariz but the naive baysian showed that the implied probaiblities were not harmonous across the series and individual games
🔴🔴🔴 we also need to model when our prices are best accurate. if we model player prob of scoring X at price P, then we make a market aroudn that, then the market moves, we lose on info
-  No additional NaN handling code is needed. The existing pipeline handles it at three levels:

 1. This code: attendance=0 → NaN, unknown arena → NaN (never produces a misleading 0.0 crowd_density)
 2. _usable_factor_columns(): drops factor if <75% non-null (crowd_density will be ~97% non-null, well above threshold)
 3. _build_normal_equations_vectorized(): remaining NaN → fillna(0.0) in design matrix X (means "no crowd effect for this game" — neutral imputation)

 The above risks data issues in our regression models later in feature pipelien and strategy
- [ ] add turnover margin as a feature 
- [ ] 🔴🔴 OUR DATA IS MESSY! SOME ARE MISSING
- [ ] We need to analyze regime changes like the 3pt revolution
- [ ] Should we do masseys per quarter? Yes, so that we canc calcualte longshot-favorite bias and see truth of wins
- [ ] 🟡 add market taking at end of game strat (eg. if team is up by 10 pts or some shit just buy the winner)
- [ ] reminder: data and features being clean and representative are always the biggest advantages
- [ ] 🔴 add kalshi connection and automatic updates to game data using apis
- [ ] 🔴 add automatic data curatoin for all parquets
- [ ] 🔴 We need playbyplayv3 data and autoupdateing/syncing of data curation (this is done with containerized lambda functions)
- How do we backtest if our probabilities are right? CHeck if we shuffle our data in kfoldig (we shouldnt)
- [ ] 🔴 Add more features for eveything
    - look into FiveThirtyEight's RAPTOR model
    - add record vs that team and variance as a feature
    - add 4 factors if it isn't already (esp as a linear comb): eFG% (40%), TOV% (25%), Offensive Rebound % (20%), Free Throw Rate (15%)
    - add "desperation" and momentum. if a team is head to ehad in series liek 3-3 and is playing at home or playing away, how do they do?
    - comparative massey ratings (Since current features i think just takes into account just the individual massey ratings. i want to see the difference in massey rating)
- [ ] maybe even live data
    - specifically, lambda is to sync. look at the keys-plan.md
- [ ] 🔴🔴 check if our k fold is chronological or not (if it isn't we need to purge and embargo if needed). so either groupkfold or time series forward chaining
- [ ] Try targeting a strat to find who will win rather than just being a trader: Among all base models. AdaBoost (81.10%), XGBoost (81.03%), and Logistic Regression (80.49%) achieved relatively high prediction accuracy. KNN (80.15%) and Naive Bayes (76.56%) performed moderately well... (from Stacked ensemble model for NBA game outcome prediction analysis)
- [ ] The findings are as follows: (1) XGBoost demonstrates excellent performance in predicting CBA game outcomes. (2) eFG%, 3P%, 2P%, ORB%, DRB, and TOV% are key indicators influencing CBA game outcomes. (3) There is a tendency for offensive play over defensive strategies in CBA playoffs. (from Explaining basketball game performance with SHAP: insights from Chinese Basketball Association)
- https://www.nature.com/articles/s41598-025-98877-1?fromPaywallRec=false#Sec20
    for analyzing movement

- should we be filling NANs with col medians
 2. data.py

 - Load game_features.parquet from the appropriate target directory
 - Filter to valid rows (non-null target), align feature columns to feature_list.txt
 - Fillna with column medians (matches feature pipeline)
 - Return (X, y, seasons, game_dates) — seasons used for LOYO CV