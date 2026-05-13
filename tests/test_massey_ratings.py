import os
import sys
import unittest

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


from nba.feature_pipeline.engineering.massey_ratings import (  # noqa: E402
    MasseyDesign,
    build_massey_matchup_diffs,
    build_massey_team_features,
    build_pregame_massey_game_features,
    fit_massey,
    format_massey_matrix_report,
)


def balanced_home_away_games():
    rows = []
    strengths = {1: 8.0, 2: 0.0, 3: -8.0}
    home_advantage = 3.0
    game_id = 1
    for home, away in [(1, 2), (2, 1), (1, 3), (3, 1), (2, 3), (3, 2)]:
        home_margin = strengths[home] - strengths[away] + home_advantage
        rows.append(
            {
                "season": 2025,
                "game_id": str(game_id),
                "game_date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=game_id),
                "home_team_id": home,
                "away_team_id": away,
                "home_score": 100 + home_margin,
                "away_score": 100,
                "attendance": 18000 + game_id,
                "capacity": 20000,
                "away_avg_experience": 5.0,
                "travel_distance_miles": 500 + 10 * game_id,
                "travel_direction": "east" if game_id % 2 else "west",
            }
        )
        game_id += 1
    return pd.DataFrame(rows)


class MasseyRatingsTest(unittest.TestCase):
    def test_location_adjusted_recovers_home_advantage(self):
        games = balanced_home_away_games()
        fit = fit_massey(
            games,
            MasseyDesign("location_adjusted_massey", include_home_advantage=True),
            season=2025,
        )

        ratings = fit.ratings.set_index("team_id")["location_adjusted_massey"]
        self.assertAlmostEqual(ratings.loc[1], 8.0, places=6)
        self.assertAlmostEqual(ratings.loc[2], 0.0, places=6)
        self.assertAlmostEqual(ratings.loc[3], -8.0, places=6)
        self.assertAlmostEqual(fit.coefficients["home_advantage"], 3.0, places=6)
        self.assertEqual(fit.solver, "numpy.linalg.solve")

    def test_design_matrix_preview_contains_expected_incidence(self):
        games = balanced_home_away_games()
        fit = fit_massey(
            games,
            MasseyDesign("location_adjusted_massey", include_home_advantage=True),
            season=2025,
        )

        first = fit.x_preview.iloc[0]
        self.assertEqual(first["team_1"], 1.0)
        self.assertEqual(first["team_2"], -1.0)
        self.assertEqual(first["team_3"], 0.0)
        self.assertEqual(first["home_advantage"], 1.0)
        self.assertIn("M = X.T @ W @ X", format_massey_matrix_report(fit))

    def test_build_team_features_and_matchup_diffs(self):
        games = balanced_home_away_games()
        features, coefficients, _ = build_massey_team_features(
            games,
            designs=(MasseyDesign("default_massey"),),
        )
        self.assertIn("default_massey", features.columns)
        self.assertIn("default_massey_rank", features.columns)
        self.assertFalse(coefficients.empty)

        matchups = pd.DataFrame({"season": [2025], "team_a_id": [1], "team_b_id": [3]})
        diffs = build_massey_matchup_diffs(matchups, features)
        expected = (
            features.loc[features["team_id"] == 1, "default_massey"].iloc[0]
            - features.loc[features["team_id"] == 3, "default_massey"].iloc[0]
        )
        self.assertAlmostEqual(diffs.loc[0, "diff_default_massey"], expected)

    def test_disconnected_schedule_gets_component_constraints(self):
        games = pd.DataFrame(
            [
                {
                    "season": 2025,
                    "game_id": "a",
                    "game_date": "2025-01-01",
                    "home_team_id": 1,
                    "away_team_id": 2,
                    "home_score": 110,
                    "away_score": 100,
                },
                {
                    "season": 2025,
                    "game_id": "b",
                    "game_date": "2025-01-01",
                    "home_team_id": 3,
                    "away_team_id": 4,
                    "home_score": 103,
                    "away_score": 100,
                },
            ]
        )
        fit = fit_massey(games, MasseyDesign("default_massey"), season=2025)
        self.assertEqual(len(fit.components), 2)
        self.assertTrue(any("disconnected" in note for note in fit.warnings))
        for comp in fit.components:
            comp_ratings = fit.ratings[fit.ratings["team_id"].isin(comp)]["default_massey"]
            self.assertAlmostEqual(float(comp_ratings.sum()), 0.0)

    def test_pregame_features_use_prior_games(self):
        games = balanced_home_away_games()
        features, coefficients = build_pregame_massey_game_features(
            games,
            designs=(MasseyDesign("default_massey"),),
            min_completed_games=1,
        )
        self.assertEqual(len(features), len(games))
        self.assertIn("diff_default_massey", features.columns)
        self.assertTrue(features["diff_default_massey"].isna().iloc[0])
        self.assertFalse(features["diff_default_massey"].isna().iloc[-1])
        self.assertFalse(coefficients.empty)


if __name__ == "__main__":
    unittest.main()
