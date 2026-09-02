# NBA Prediction Markets

A machine-learning pipeline for predicting NBA game outcomes and trading the
corresponding markets on Kalshi. The project is currently inactive/abandoned;
this README describes the codebase as it stands, not a maintained product.

The pipeline runs in five stages:

```
data_curation  ->  feature_pipeline  ->  strategy  ->  backtest  ->  trading
```

Multi-league support (`league_config.py`) was added partway through
development; NBA is the primary/complete league, and there is partial WNBA
data under `data_curation/data_wnba/`.

## Directory Layout

- **`data_curation/`** — Fetches and normalizes raw NBA data (box scores,
  advanced stats, hustle stats, rosters, officials, ratings) from nba_api,
  ESPN, and Sagarin, storing everything as parquet files in `data/`. Entry
  point: `data_curation/scripts/sync_games.py`. See
  `data_curation/README.md` and `data_curation/data/SCHEMA.md`.

- **`feature_pipeline/`** — Builds game-level feature rows from the raw data
  and ranks features for predictive signal using MDI/MDA/SFI/PCA (de Prado
  framework), guarding against leakage and multicollinearity. Entry points:
  `feature_pipeline/build_features_only.py` (features only) and
  `feature_pipeline/analysis/run.py` (features + importance analysis). See
  `feature_pipeline/README.md` and `feature_pipeline/FEATURES.md`.

- **`strategy/`** — Trains and evaluates models (LightGBM, XGBoost,
  CatBoost, logistic/linear models, etc.) against several prediction targets
  (winner, spread, total, first-half variants), using purged/year-based
  cross-validation to avoid temporal leakage. Includes feature routing,
  forward selection, and ensembling of per-model "specialists". Entry point:
  `strategy/run.py` (`python -m strategy.run --league nba --target winner`).
  See `strategy/README.md` and `feature_pipeline/TARGETS.md`.

- **`backtest/`** — Simulates trading model predictions against historical
  Kalshi market data: fetches candlesticks/trade tape
  (`download_kalshi_history.py`), matches predictions to markets, computes
  quotes, and estimates fill/PnL under different execution assumptions
  (`run.py`, `longshot_bias.py`, `flb/`). `kalshi_client.py` is the shared
  Kalshi REST API client (RSA-PSS request signing).

- **`trading/`** — The live/paper trading loop: scans upcoming games,
  generates signals across all Kalshi NBA market types (winner, spread,
  total, first-half), sizes positions (Kelly-based with correlation-cluster
  caps), and executes or logs orders (`runner.py`, `scanner.py`, `sizing.py`,
  `executor.py`, `portfolio.py`, `risk.py`, `ws.py` for the market
  WebSocket). See `trading/README.md` for the detailed design.

- **`tests/`** — Pytest unit tests covering data sync, Massey ratings,
  feature/game-row building, and league config, run with `pytest tests/`.

- **`notebooks/`** — Ad hoc exploration notebooks, not part of the
  pipeline.

- **`scripts/`** — Standalone analysis scripts not part of the core
  pipeline (e.g. comparing model Brier scores to Kalshi market pricing).

- **`research/`** — Reference material (a paper on defensive strategy
  analysis) consulted during feature design.

## Configuration and Credentials

- `league_config.py` is the shared source of truth for per-league constants
  (data paths, output paths, file names); most scripts take a `--league`
  flag.
- Kalshi API credentials are read from a local `.env` file plus RSA private
  key files referenced by `backtest/kalshi_client.py`. None of these are
  committed to the repository — see `.gitignore`. Anyone reusing this code
  needs to supply their own Kalshi API key/private key pair.

## Documentation

- `CLAUDE.md` — project conventions used when this repo was developed with
  an AI coding assistant (methodology, leakage-prevention rules, etc.).
- `feature_pipeline/FEATURES.md` — feature inventory.
- `feature_pipeline/TARGETS.md` — prediction target definitions.
- `TODOS.md` — outstanding work items as of when the project was paused.
- Per-module `README.md` files listed above go into more detail than this
  file.

## Setup

Dependencies are listed in `requirements.txt` (full conda export) and
`requirements_clean.txt` (trimmed, pip-installable subset). There is no
packaging/build step; modules are run directly with `python -m`.
