# Prediction Targets

## Active (implemented)
- `target_winner` — binary (1 = home wins)
- `target_home_score` — home team final points
- `target_away_score` — away team final points
- `target_spread` — home_score - away_score
- `target_total` — home_score + away_score (over/under)
- `target_h1_spread` — first half spread (requires quarter scores)
- `target_h2_spread` — second half spread
- `target_h1_total` — first half total points
- `target_h2_total` — second half total points
- `target_home_wins_h1` — who leads at halftime
- `target_home_wins_h2` — who wins the second half
- `target_overtime` — binary (1 = game goes to OT)
- `target_series_winner` — who wins the playoff series (playoffs only)
- `target_series_total_games` — how many games the series goes (4-7)
- `target_series_spread` — series wins margin (e.g., 4-2 → spread of 2)
- `target_series_exact` — exact series result (4-0, 4-1, 4-2, 4-3)

## Deferred (need additional data)
- Player performance (final points, rebounds, assists, etc.)
- Point leader / rebound leader per game
- Probability Team A ahead by X at half N
