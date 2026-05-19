# ESPN vs NBA API Coverage

This compares the local docs in:

- `nba/api_docs/nba_api_docs/docs`
- `nba/api_docs/espn_api_docs/docs`

## Bottom line

If your goal is basketball analytics, modeling, and feature engineering, the NBA API has much deeper coverage for on-court stats.

If your goal is product-style sports data like schedules, standings, rosters, injuries, news, betting context, and consumer-friendly game summaries across multiple leagues, ESPN has broader coverage.

## Documentation shape

### NBA API docs

- The NBA docs are endpoint-first and very granular.
- There are `135` stats endpoint docs plus `4` live endpoint docs in this repo.
- Most endpoint docs include:
  - a valid sample URL
  - required parameters
  - documented dataset names
  - documented output columns
- The responses are mostly tabular and fit well into pandas workflows.

### ESPN API docs

- The ESPN docs are domain-first and less granular for NBA specifically.
- The basketball doc groups coverage into broad families like seasons, teams, athletes, events, rankings, and site resources.
- In the basketball doc, there are roughly:
  - `45` core API endpoint patterns
  - `21` Site API resource patterns
  - `5` CDN game-package examples
  - `5` athlete/common-v3 examples
- ESPN response docs focus on nested JSON schemas rather than dataframe-like tables.

## Coverage comparison

| Area | NBA API | ESPN API | Better coverage |
|---|---|---|---|
| Box scores | Very deep: traditional, advanced, misc, four factors, usage, matchups, summary, scoring, hustle | Present through summary and CDN game package | NBA API |
| Play-by-play | Deep: `PlayByPlay`, `PlayByPlayV2`, `WinProbabilityPBP`, video/event endpoints | Present in summary/CDN package, plus probabilities | NBA API |
| Player tracking / matchup data | Strong: matchup, shot defense, pass, rebound, shot locations, on/off, lineup and team-vs-player views | Not documented at that level | NBA API |
| Shot charts / spatial data | Strong: shot chart detail, lineup detail, league-wide shot charts, player/team shot locations | Not documented at that level | NBA API |
| Split dashboards | Strong: clutch, game splits, shooting splits, last N games, team performance, year-over-year | Athlete splits exist, but much thinner | NBA API |
| Team/player advanced metrics | Strong: estimated metrics, hustle, synergy, four factors, usage, pt defend, pt stats | Mostly summary-style or leader-style stats | NBA API |
| Historical basketball stats | Strong: all-time leaders, franchise history/leaders, draft combine/history, career stats | Some season, athlete, team, draft, and standings coverage | NBA API |
| Video-linked data | Present: `VideoDetails`, `VideoDetailsAsset`, `VideoEvents`, `VideoStatus` | Not a comparable basketball-specific video stats surface in docs | NBA API |
| Standings / records | Present | Present and more product-friendly | Slight ESPN edge for presentation |
| Rosters / teams / athletes | Present | Present with richer profile-style objects and cross-links | ESPN |
| Injuries | Not a core strength in these docs | Strong: team injuries and league-wide injuries | ESPN |
| Transactions | Not covered in your NBA docs set | Covered | ESPN |
| News / editorial | Not covered | Covered: team news, athlete news, now feed | ESPN |
| Depth charts | Not covered | Covered | ESPN |
| Betting odds | Present in live `Odds` endpoint, but narrower docs | Covered in core odds plus CDN/game package context | ESPN |
| Multi-league basketball | Mostly NBA ecosystem plus WNBA/G League/live docs around NBA package | Broad: NBA, WNBA, NCAA men/women, FIBA, NBL, Olympics, summer leagues | ESPN |

## What NBA API clearly gives you that ESPN does not document as well

- Fine-grained statistical endpoints for nearly every analysis slice.
- Data built for direct modeling:
  - per-player box features
  - per-team box features
  - lineup features
  - matchup features
  - shot-location features
  - clutch and split features
  - tracking-style aggregates
- Better support for reproducible tabular extraction because docs list exact dataset columns.

Examples from your local NBA docs:

- `LeagueDashPlayerStats`, `LeagueDashTeamStats`
- `LeagueDashLineups`, `TeamDashLineups`
- `PlayerDashPtPass`, `PlayerDashPtReb`, `PlayerDashPtShots`, `PlayerDashPtShotDefend`
- `ShotChartDetail`, `ShotChartLeagueWide`, `ShotChartLineupDetail`
- `PlayerDashboardByGeneralSplits`, `PlayerDashboardByShootingSplits`, `PlayerDashboardByClutch`
- `TeamPlayerOnOffDetails`, `TeamPlayerOnOffSummary`
- `BoxScoreAdvancedV2`, `BoxScoreFourFactorsV2`, `BoxScoreUsageV2`, `BoxScoreMatchupsV3`
- `WinProbabilityPBP`, `VideoEvents`

## What ESPN clearly gives you that NBA API does not document as well

- More consumer/product coverage around teams and games.
- Better non-stat context:
  - injuries
  - transactions
  - news
  - records
  - depth charts
  - broadcasts
  - venue and attendance context
  - provider-specific betting odds
- Easier cross-league portability if you want one API style for NBA, WNBA, NCAA, FIBA, and more.

Examples from your local ESPN docs:

- `scoreboard`
- `teams/{id}/roster`
- `teams/{id}/schedule`
- `teams/{id}/record`
- `teams/{id}/injuries`
- `transactions`
- `news`
- `summary?event={id}`
- `statistics/byathlete`
- CDN game package with plays, scoring, odds, and win probability

## Structure differences

### NBA API structure

- Best when you want dataframes.
- Endpoint docs describe output in column form.
- Easier to normalize into fact tables.
- Better for ML feature pipelines and historical backfills.

### ESPN API structure

- Best when you want nested objects ready for app/backend consumption.
- Strong use of linked `$ref` objects and summary packages.
- Easier to power scoreboards, team pages, injury/news views, and cross-league browsing.
- More normalization work is needed before analytics-heavy modeling.

## Practical recommendation

For your prediction-markets workflow:

- Use the NBA API as the primary stats source.
- Use ESPN as a complementary context source.

Best split of responsibilities:

- NBA API for:
  - game-level and player-level modeling features
  - lineup/on-off features
  - shot profile features
  - advanced box and matchup features
  - historical stat backfills

- ESPN for:
  - injury status
  - news/event context
  - schedule presentation
  - team metadata
  - betting and broadcast context
  - cross-league expansion

## Important caveat

This comparison is based on the local docs in this repo, not a live scrape of either API on May 5, 2026. It reflects documented coverage here, which is enough to compare feature surface area, but not necessarily every currently live endpoint.
