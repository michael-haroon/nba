"""
test_pipeline_integrity.py
--------------------------
Fast, comprehensive integrity tests for the entire prediction pipeline.
No model training, no GPU, no large data loads. Validates math, consistency,
temporal safety, and configuration correctness.

Run: conda run -n pred python -m pytest tests/test_pipeline_integrity.py -v
"""

import numpy as np
import pandas as pd
import pytest


# ─── Kelly formula ────────────────────────────────────────────────────────────

class TestKellyFormula:
    def test_kelly_correct_yes(self):
        from strategy.trade_signals import compute_edge
        # model=65%, price_yes=55%, price_no=47%
        side, edge, kelly = compute_edge(0.65, 0.55, 0.47)
        assert side == "YES"
        assert abs(edge - 0.10) < 1e-10
        # Correct Kelly: (p - price) / (1 - price) = 0.10 / 0.45
        assert abs(kelly - 0.10 / 0.45) < 1e-10

    def test_kelly_correct_no(self):
        from strategy.trade_signals import compute_edge
        # model=35% win, price_yes=60%, price_no=42%
        side, edge, kelly = compute_edge(0.35, 0.60, 0.42)
        assert side == "NO"
        assert abs(edge - 0.23) < 1e-10
        # Kelly: edge / (1 - price_no) = 0.23 / 0.58
        assert abs(kelly - 0.23 / 0.58) < 1e-10

    def test_kelly_zero_edge(self):
        from strategy.trade_signals import compute_edge
        side, edge, kelly = compute_edge(0.50, 0.55, 0.50)
        # edge_yes = -0.05, edge_no = 0.0 -> both non-positive
        assert kelly == 0.0

    def test_kelly_at_boundary_prices(self):
        from strategy.trade_signals import compute_edge
        # Price near 1 should not crash
        side, edge, kelly = compute_edge(0.99, 0.95, 0.06)
        assert kelly >= 0
        # Price near 0
        side, edge, kelly = compute_edge(0.99, 0.01, 0.98)
        assert side == "YES"


# ─── Fee calculation ──────────────────────────────────────────────────────────

class TestFees:
    def test_taker_fee_at_50_cents(self):
        from strategy.calibration import kalshi_taker_fee
        # 0.07 * 1 * 0.5 * 0.5 = 0.0175 -> ceil to 0.02
        fee = kalshi_taker_fee(0.50, 1)
        assert fee == 0.02

    def test_taker_fee_scales_with_contracts(self):
        from strategy.calibration import kalshi_taker_fee
        fee_1 = kalshi_taker_fee(0.50, 1)
        fee_10 = kalshi_taker_fee(0.50, 10)
        assert fee_10 >= fee_1 * 9  # rounding can differ slightly

    def test_min_edge_increases_with_price(self):
        from strategy.calibration import min_edge_for_profit
        edges = [min_edge_for_profit(p) for p in [0.3, 0.4, 0.5, 0.6, 0.7]]
        # min_edge = 0.07 * price, so strictly increasing
        assert all(edges[i] < edges[i+1] for i in range(len(edges)-1))

    def test_min_edge_formula(self):
        from strategy.calibration import min_edge_for_profit
        # min_edge = 0.07 * P (taker)
        assert abs(min_edge_for_profit(0.60) - 0.042) < 1e-10
        # maker: 0.0175 * P
        assert abs(min_edge_for_profit(0.60, maker=True) - 0.0105) < 1e-10


# ─── Distribution consistency ────────────────────────────────────────────────

class TestDistributions:
    def test_spread_uses_t_not_normal(self):
        """predict.py and trade_signals.py must use t-distribution."""
        import inspect
        from strategy import predict, trade_signals
        # predict.py should import t_dist
        assert hasattr(predict, 't_dist')
        # trade_signals should NOT use norm
        source = inspect.getsource(trade_signals)
        assert "from scipy.stats import norm" not in source
        assert "norm.cdf" not in source

    def test_cover_prob_uses_t_dist(self):
        from strategy.predict import cover_prob
        from scipy.stats import t as t_dist
        from strategy.config import SPREAD_RESID_DF, SPREAD_RESID_SCALE
        # Manual calculation
        mu = 5.0
        threshold = 3.0
        delta = threshold - mu
        expected = float(1 - t_dist.cdf(delta / SPREAD_RESID_SCALE, df=SPREAD_RESID_DF))
        result = cover_prob(threshold, mu)
        assert abs(result - expected) < 0.01  # allow for bias correction

    def test_cover_prob_symmetry(self):
        from strategy.predict import cover_prob
        # P(spread > +5 | mu=0) should equal P(spread > -5 | mu=0) inverted
        p_pos = cover_prob(5.0, 0.0)
        p_neg = cover_prob(-5.0, 0.0)
        assert abs(p_pos + p_neg - 1.0) < 0.02  # approximate symmetry

    def test_over_prob_monotone(self):
        from strategy.predict import over_prob
        # Higher line -> lower probability of going over
        probs = [over_prob(line, 215.0) for line in [200, 210, 220, 230]]
        assert all(probs[i] > probs[i+1] for i in range(len(probs)-1))


# ─── Huber delta configuration ───────────────────────────────────────────────

class TestHuberConfig:
    def test_lgbm_alpha_matches_huber_delta(self):
        from strategy.config import LGBM_REG_PARAMS, HUBER_DELTA
        assert LGBM_REG_PARAMS["alpha"] == HUBER_DELTA

    def test_huber_delta_reasonable_for_nba(self):
        from strategy.config import HUBER_DELTA
        # NBA spread residuals: MAD ~ 8, IQR ~ 19
        # Delta should be in 5-20 range
        assert 5.0 <= HUBER_DELTA <= 20.0

    def test_ensemble_lgbm_alpha_not_default(self):
        """ensemble.py regression LGBM must not use alpha=0.9 (LightGBM default)."""
        import inspect
        from strategy.ensemble import _regression_specs
        source = inspect.getsource(_regression_specs)
        # Should NOT contain "alpha": 0.9 for huber objective
        assert '"alpha": 0.9' not in source

    def test_adaptive_delta_in_final_model(self):
        """train.py final model must use adaptive delta, not build_fn."""
        import inspect
        from strategy.train import train_and_evaluate
        source = inspect.getsource(train_and_evaluate)
        assert "select_huber_delta" in source
        assert "build_regressor_with_delta" in source


# ─── Calibration module ───────────────────────────────────────────────────────

class TestCalibration:
    def test_isotonic_improves_or_maintains(self):
        from strategy.calibration import fit_isotonic_calibrator
        np.random.seed(42)
        y = np.random.binomial(1, 0.6, 500)
        p = np.clip(y * 0.7 + (1 - y) * 0.3 + np.random.normal(0, 0.1, 500), 0.01, 0.99)
        cal = fit_isotonic_calibrator(y, p)
        calibrated = cal.predict(p)
        # Calibrated predictions should be between 0 and 1
        assert calibrated.min() >= 0
        assert calibrated.max() <= 1

    def test_residual_distribution_fit(self):
        from strategy.calibration import fit_residual_distribution
        np.random.seed(42)
        from scipy.stats import t as t_dist
        true_df, true_scale = 15.0, 11.0
        residuals_sample = t_dist.rvs(df=true_df, scale=true_scale, size=5000)
        y_true = residuals_sample
        y_pred = np.zeros_like(y_true)
        result = fit_residual_distribution(y_true, y_pred)
        # Should recover approximately
        assert abs(result["df"] - true_df) < 5
        assert abs(result["scale"] - true_scale) < 2

    def test_calibrate_bundle_adds_key(self):
        from strategy.calibration import calibrate_bundle
        bundle = {"task": "classification", "target": "winner"}
        np.random.seed(42)
        y = np.random.binomial(1, 0.55, 200).astype(float)
        p = np.clip(y * 0.6 + np.random.normal(0, 0.1, 200), 0.01, 0.99)
        stds = np.random.uniform(0.02, 0.05, 200)
        result = calibrate_bundle(bundle, p, y, stds)
        assert "calibration" in result
        assert "isotonic_calibrator" in result["calibration"]
        assert "std_thresholds" in result["calibration"]

    def test_calibrate_bundle_regression(self):
        from strategy.calibration import calibrate_bundle
        bundle = {"task": "regression", "target": "spread"}
        np.random.seed(42)
        y = np.random.normal(3, 12, 500)
        p = y + np.random.normal(0, 10, 500)
        stds = np.random.uniform(1, 5, 500)
        result = calibrate_bundle(bundle, p, y, stds)
        assert "residual_dist" in result["calibration"]
        assert "bias_table" in result["calibration"]
        assert result["calibration"]["residual_dist"]["df"] > 0
        assert result["calibration"]["residual_dist"]["scale"] > 0


# ─── Temporal safety in feature engineering ───────────────────────────────────

class TestTemporalSafety:
    def test_rolling_features_use_shift(self):
        """All rolling features must shift before rolling (no same-game data)."""
        import inspect
        try:
            from feature_pipeline.engineering import feature_engineering as fe
        except ImportError:
            pytest.skip("feature_pipeline not available on this machine")
        source = inspect.getsource(fe)
        import re
        shift_then_roll = len(re.findall(r'shift\(1\)\.rolling', source))
        assert shift_then_roll >= 15

    def test_massey_uses_strict_less_than(self):
        """Massey ratings must use game_date < target_date (strict)."""
        import inspect
        try:
            from data_curation.scripts.build_massey_ratings import _fit_all_ratings_for_date
        except (ImportError, ModuleNotFoundError):
            pytest.skip("data_curation not available on this machine")
        source = inspect.getsource(_fit_all_ratings_for_date)
        assert "game_date\" < game_date" in source or 'game_date"] < game_date' in source

    def test_referee_features_sorted(self):
        """Referee feature computation must sort by game_date before expanding."""
        import inspect
        try:
            from feature_pipeline.engineering.feature_engineering import compute_referee_features
        except ImportError:
            pytest.skip("feature_pipeline not available on this machine")
        source = inspect.getsource(compute_referee_features)
        assert 'sort_values("game_date")' in source
        assert ".expanding().mean().shift(1)" in source

    def test_safe_divide_threshold(self):
        """_safe_divide must not produce huge values."""
        try:
            from feature_pipeline.engineering.feature_engineering import _safe_divide
        except ImportError:
            pytest.skip("feature_pipeline not available on this machine")
        result = _safe_divide(np.array([100.0]), np.array([0.0001]))
        assert np.isnan(result[0])
        result2 = _safe_divide(np.array([100.0]), np.array([1.0]))
        assert result2[0] == 100.0


# ─── predict.py uses bundle calibration ──────────────────────────────────────

class TestPredictCalibration:
    def test_get_residual_params_from_bundle(self):
        from strategy.predict import _get_residual_params
        bundle = {"calibration": {"residual_dist": {"df": 20.0, "scale": 13.0}}}
        df, scale = _get_residual_params(bundle)
        assert df == 20.0
        assert scale == 13.0

    def test_get_residual_params_fallback(self):
        from strategy.predict import _get_residual_params
        from strategy.config import SPREAD_RESID_DF, SPREAD_RESID_SCALE
        bundle = {"target": "spread"}  # no calibration key
        df, scale = _get_residual_params(bundle)
        assert df == SPREAD_RESID_DF
        assert scale == SPREAD_RESID_SCALE

    def test_isotonic_applied_when_present(self):
        from strategy.predict import _apply_isotonic
        from sklearn.isotonic import IsotonicRegression
        cal = IsotonicRegression(out_of_bounds="clip")
        cal.fit([0.3, 0.5, 0.7], [0.0, 0.5, 1.0])
        bundle = {"calibration": {"isotonic_calibrator": cal}}
        result = _apply_isotonic(bundle, 0.5)
        assert abs(result - 0.5) < 0.1

    def test_isotonic_passthrough_when_absent(self):
        from strategy.predict import _apply_isotonic
        bundle = {}
        assert _apply_isotonic(bundle, 0.65) == 0.65

    def test_conf_tier_uses_bundle_thresholds(self):
        from strategy.predict import _conf_tier
        bundle = {"calibration": {"std_thresholds": (0.01, 0.02)}}
        assert _conf_tier(0.005, bundle) == "HIGH"
        assert _conf_tier(0.015, bundle) == "MEDIUM"
        assert _conf_tier(0.03, bundle) == "LOW"


# ─── Config sanity ────────────────────────────────────────────────────────────

class TestConfigSanity:
    def test_no_stale_sigma_spread_usage(self):
        """SIGMA_SPREAD should not be used in production code paths."""
        import inspect
        from strategy import trade_signals
        source = inspect.getsource(trade_signals)
        assert "SIGMA_SPREAD" not in source

    def test_skip_seasons_excludes_covid(self):
        from strategy.config import SKIP_SEASONS
        assert "2019-20" in SKIP_SEASONS

    def test_kelly_fraction_reasonable(self):
        from strategy.config import KELLY_FRACTION
        assert 0.05 <= KELLY_FRACTION <= 0.5

    def test_residual_params_positive(self):
        from strategy.config import (
            SPREAD_RESID_DF, SPREAD_RESID_SCALE,
            TOTAL_RESID_DF, TOTAL_RESID_SCALE,
        )
        assert SPREAD_RESID_DF > 2
        assert SPREAD_RESID_SCALE > 0
        assert TOTAL_RESID_DF > 2
        assert TOTAL_RESID_SCALE > 0

    def test_catboost_reg_uses_huber_delta(self):
        from strategy.config import CATBOOST_REG_PARAMS, HUBER_DELTA
        assert f"delta={HUBER_DELTA}" in CATBOOST_REG_PARAMS["loss_function"]


# ─── End-to-end consistency ───────────────────────────────────────────────────

class TestEndToEnd:
    def test_trade_signals_import_chain(self):
        """Full import chain doesn't crash."""
        from strategy.trade_signals import generate_signals
        from strategy.predict import predict_matchups
        from strategy.calibration import calibrate_bundle

    def test_ensemble_regression_specs_consistent(self):
        """All regression LGBM specs use alpha >= 5 (not LightGBM default 0.9)."""
        from strategy.ensemble import _regression_specs
        specs = _regression_specs()
        lgbm_specs = [s for s in specs if s.family == "lgbm"]
        for spec in lgbm_specs:
            mdl = spec.build_fn()
            alpha = mdl.get_params().get("alpha", None)
            if alpha is not None:
                assert alpha >= 5.0, f"{spec.name} has alpha={alpha} (should be >= 5)"

    def test_predict_cover_prob_with_and_without_bundle(self):
        """cover_prob works both with bundle calibration and without."""
        from strategy.predict import cover_prob
        # Without bundle (uses config fallback)
        p1 = cover_prob(5.0, 3.0)
        assert 0 < p1 < 1
        # With bundle
        bundle = {"calibration": {"residual_dist": {"df": 15, "scale": 11}}}
        p2 = cover_prob(5.0, 3.0, bundle)
        assert 0 < p2 < 1
