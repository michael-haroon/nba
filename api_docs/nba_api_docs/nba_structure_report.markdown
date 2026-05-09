# NBA Endpoint Samples

Generated from the markdown docs in `api_docs/nba_api_docs/docs`.

## AllTimeLeadersGrids

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/alltimeleadersgrids.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/alltimeleadersgrids?LeagueID=00&PerMode=Totals&SeasonType=Regular+Season&TopX=10`

```python
from nba_api.stats.endpoints import alltimeleadersgrids
endpoint = alltimeleadersgrids.AllTimeLeadersGrids(
    league_id='00',
    per_mode_simple='Totals',
    season_type='Regular Season',
    topx=10,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ASTLeaders (`ast_leaders`): PLAYER_ID, PLAYER_NAME, AST, AST_RANK
- BLKLeaders (`blk_leaders`): PLAYER_ID, PLAYER_NAME, BLK, BLK_RANK
- DREBLeaders (`dreb_leaders`): PLAYER_ID, PLAYER_NAME, DREB, DREB_RANK
- FG3ALeaders (`fg3_a_leaders`): PLAYER_ID, PLAYER_NAME, FG3A, FG3A_RANK
- FG3MLeaders (`fg3_m_leaders`): PLAYER_ID, PLAYER_NAME, FG3M, FG3M_RANK
- FG3_PCTLeaders (`fg3_pct_leaders`): PLAYER_ID, PLAYER_NAME, FG3_PCT, FG3_PCT_RANK
- FGALeaders (`fga_leaders`): PLAYER_ID, PLAYER_NAME, FGA, FGA_RANK
- FGMLeaders (`fgm_leaders`): PLAYER_ID, PLAYER_NAME, FGM, FGM_RANK
- FG_PCTLeaders (`fg_pct_leaders`): PLAYER_ID, PLAYER_NAME, FG_PCT, FG_PCT_RANK
- FTALeaders (`fta_leaders`): PLAYER_ID, PLAYER_NAME, FTA, FTA_RANK
- FTMLeaders (`ftm_leaders`): PLAYER_ID, PLAYER_NAME, FTM, FTM_RANK
- FT_PCTLeaders (`ft_pct_leaders`): PLAYER_ID, PLAYER_NAME, FT_PCT, FT_PCT_RANK
- GPLeaders (`g_p_leaders`): PLAYER_ID, PLAYER_NAME, GP, GP_RANK
- OREBLeaders (`oreb_leaders`): PLAYER_ID, PLAYER_NAME, OREB, OREB_RANK
- PFLeaders (`pf_leaders`): PLAYER_ID, PLAYER_NAME, PF, PF_RANK
- PTSLeaders (`pts_leaders`): PLAYER_ID, PLAYER_NAME, PTS, PTS_RANK
- REBLeaders (`reb_leaders`): PLAYER_ID, PLAYER_NAME, REB, REB_RANK
- STLLeaders (`stl_leaders`): PLAYER_ID, PLAYER_NAME, STL, STL_RANK
- TOVLeaders (`tov_leaders`): PLAYER_ID, PLAYER_NAME, TOV, TOV_RANK

## AssistLeaders

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/assistleaders.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/assistleaders?LeagueID=00&PerMode=Totals&PlayerOrTeam=Team&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import assistleaders
endpoint = assistleaders.AssistLeaders(
    league_id='00',
    per_mode_simple='Totals',
    player_or_team='Team',
    season='2019-20',
    season_type_playoffs='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AssistLeaders (`assist_leaders`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, AST

## AssistTracker

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/assisttracker.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/assisttracker?College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&GameScope=&Height=&LastNGames=&LeagueID=&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=&PlayerExperience=&PlayerPosition=&Season=&SeasonSegment=&SeasonType=&StarterBench=&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import assisttracker
endpoint = assisttracker.AssistTracker(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_scope_simple_nullable="",
    height_nullable="",
    last_n_games_nullable="",
    league_id_nullable="",
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple_nullable="",
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    season_nullable="",
    season_segment_nullable="",
    season_type_all_star_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AssistTracker (`assist_tracker`): ASSISTS

## BoxScoreAdvancedV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscoreadvancedv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscoreadvancedv2?EndPeriod=1&EndRange=0&GameID=0021700807&RangeType=0&StartPeriod=1&StartRange=0`

```python
from nba_api.stats.endpoints import boxscoreadvancedv2
endpoint = boxscoreadvancedv2.BoxScoreAdvancedV2(
    end_period=1,
    end_range=0,
    game_id='0021700807',
    range_type=0,
    start_period=1,
    start_range=0,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerStats (`player_stats`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MIN, E_OFF_RATING, OFF_RATING, E_DEF_RATING, DEF_RATING, E_NET_RATING, NET_RATING, AST_PCT, AST_TOV, AST_RATIO, OREB_PCT, DREB_PCT, REB_PCT, TM_TOV_PCT, EFG_PCT, TS_PCT, USG_PCT, E_USG_PCT, E_PACE, PACE, PACE_PER40, POSS, PIE
- TeamStats (`team_stats`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MIN, E_OFF_RATING, OFF_RATING, E_DEF_RATING, DEF_RATING, E_NET_RATING, NET_RATING, AST_PCT, AST_TOV, AST_RATIO, OREB_PCT, DREB_PCT, REB_PCT, E_TM_TOV_PCT, TM_TOV_PCT, EFG_PCT, TS_PCT, USG_PCT, E_USG_PCT, E_PACE, PACE, PACE_PER40, POSS, PIE

## BoxScoreFourFactorsV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscorefourfactorsv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscorefourfactorsv2?EndPeriod=1&EndRange=0&GameID=0021700807&RangeType=0&StartPeriod=1&StartRange=0`

```python
from nba_api.stats.endpoints import boxscorefourfactorsv2
endpoint = boxscorefourfactorsv2.BoxScoreFourFactorsV2(
    end_period=1,
    end_range=0,
    game_id='0021700807',
    range_type=0,
    start_period=1,
    start_range=0,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- sqlPlayersFourFactors (`sql_players_four_factors`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MIN, EFG_PCT, FTA_RATE, TM_TOV_PCT, OREB_PCT, OPP_EFG_PCT, OPP_FTA_RATE, OPP_TOV_PCT, OPP_OREB_PCT
- sqlTeamsFourFactors (`sql_teams_four_factors`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MIN, EFG_PCT, FTA_RATE, TM_TOV_PCT, OREB_PCT, OPP_EFG_PCT, OPP_FTA_RATE, OPP_TOV_PCT, OPP_OREB_PCT

## BoxScoreMatchupsV3

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscorematchupsv3.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscorematchupsv3?GameID=0021700807`

```python
from nba_api.stats.endpoints import boxscorematchupsv3
endpoint = boxscorematchupsv3.BoxScoreMatchupsV3(
    game_id='0021700807',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerStats (`player_stats`): gameId, teamId, teamCity, teamName, teamTricode, teamSlug, personIdOff, firstNameOff, familyNameOff, nameIOff, playerSlugOff, jerseyNumOff, personIdDef, firstNameDef, familyNameDef, nameIDef, playerSlugDef, positionDef, commentDef, jerseyNumDef, matchupMinutes, matchupMinutesSort, partialPossessions, percentageDefenderTotalTime, percentageOffensiveTotalTime, percentageTotalTimeBothOn, switchesOn, playerPoints, teamPoints, matchupAssists, matchupPotentialAssists, matchupTurnovers, matchupBlocks, matchupFieldGoalsMade, matchupFieldGoalsAttempted, matchupFieldGoalsPercentage, matchupThreePointersMade, matchupThreePointersAttempted, matchupThreePointersPercentage, helpBlocks, helpFieldGoalsMade, helpFieldGoalsAttempted, helpFieldGoalsPercentage, matchupFreeThrowsMade, matchupFreeThrowsAttempted, shootingFouls

## BoxScoreMiscV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscoremiscv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscoremiscv2?EndPeriod=1&EndRange=0&GameID=0021700807&RangeType=0&StartPeriod=1&StartRange=0`

```python
from nba_api.stats.endpoints import boxscoremiscv2
endpoint = boxscoremiscv2.BoxScoreMiscV2(
    end_period=1,
    end_range=0,
    game_id='0021700807',
    range_type=0,
    start_period=1,
    start_range=0,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- sqlPlayersMisc (`sql_players_misc`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MIN, PTS_OFF_TOV, PTS_2ND_CHANCE, PTS_FB, PTS_PAINT, OPP_PTS_OFF_TOV, OPP_PTS_2ND_CHANCE, OPP_PTS_FB, OPP_PTS_PAINT, BLK, BLKA, PF, PFD
- sqlTeamsMisc (`sql_teams_misc`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MIN, PTS_OFF_TOV, PTS_2ND_CHANCE, PTS_FB, PTS_PAINT, OPP_PTS_OFF_TOV, OPP_PTS_2ND_CHANCE, OPP_PTS_FB, OPP_PTS_PAINT, BLK, BLKA, PF, PFD

## BoxScoreScoringV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscorescoringv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscorescoringv2?EndPeriod=1&EndRange=0&GameID=0021700807&RangeType=0&StartPeriod=1&StartRange=0`

```python
from nba_api.stats.endpoints import boxscorescoringv2
endpoint = boxscorescoringv2.BoxScoreScoringV2(
    end_period=1,
    end_range=0,
    game_id='0021700807',
    range_type=0,
    start_period=1,
    start_range=0,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- sqlPlayersScoring (`sql_players_scoring`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MIN, PCT_FGA_2PT, PCT_FGA_3PT, PCT_PTS_2PT, PCT_PTS_2PT_MR, PCT_PTS_3PT, PCT_PTS_FB, PCT_PTS_FT, PCT_PTS_OFF_TOV, PCT_PTS_PAINT, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM
- sqlTeamsScoring (`sql_teams_scoring`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MIN, PCT_FGA_2PT, PCT_FGA_3PT, PCT_PTS_2PT, PCT_PTS_2PT_MR, PCT_PTS_3PT, PCT_PTS_FB, PCT_PTS_FT, PCT_PTS_OFF_TOV, PCT_PTS_PAINT, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM

## BoxScoreSimilarityScore

- Status: missing docs
- Note: No matching markdown doc found in this repo.

## BoxScoreSummaryV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscoresummaryv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscoresummaryv2?GameID=0021700807`

```python
from nba_api.stats.endpoints import boxscoresummaryv2
endpoint = boxscoresummaryv2.BoxScoreSummaryV2(
    game_id='0021700807',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AvailableVideo (`available_video`): GAME_ID, VIDEO_AVAILABLE_FLAG, PT_AVAILABLE, PT_XYZ_AVAILABLE, WH_STATUS, HUSTLE_STATUS, HISTORICAL_STATUS
- GameInfo (`game_info`): GAME_DATE, ATTENDANCE, GAME_TIME
- GameSummary (`game_summary`): GAME_DATE_EST, GAME_SEQUENCE, GAME_ID, GAME_STATUS_ID, GAME_STATUS_TEXT, GAMECODE, HOME_TEAM_ID, VISITOR_TEAM_ID, SEASON, LIVE_PERIOD, LIVE_PC_TIME, NATL_TV_BROADCASTER_ABBREVIATION, LIVE_PERIOD_TIME_BCAST, WH_STATUS
- InactivePlayers (`inactive_players`): PLAYER_ID, FIRST_NAME, LAST_NAME, JERSEY_NUM, TEAM_ID, TEAM_CITY, TEAM_NAME, TEAM_ABBREVIATION
- LastMeeting (`last_meeting`): GAME_ID, LAST_GAME_ID, LAST_GAME_DATE_EST, LAST_GAME_HOME_TEAM_ID, LAST_GAME_HOME_TEAM_CITY, LAST_GAME_HOME_TEAM_NAME, LAST_GAME_HOME_TEAM_ABBREVIATION, LAST_GAME_HOME_TEAM_POINTS, LAST_GAME_VISITOR_TEAM_ID, LAST_GAME_VISITOR_TEAM_CITY, LAST_GAME_VISITOR_TEAM_NAME, LAST_GAME_VISITOR_TEAM_CITY1, LAST_GAME_VISITOR_TEAM_POINTS
- LineScore (`line_score`): GAME_DATE_EST, GAME_SEQUENCE, GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY_NAME, TEAM_NICKNAME, TEAM_WINS_LOSSES, PTS_QTR1, PTS_QTR2, PTS_QTR3, PTS_QTR4, PTS_OT1, PTS_OT2, PTS_OT3, PTS_OT4, PTS_OT5, PTS_OT6, PTS_OT7, PTS_OT8, PTS_OT9, PTS_OT10, PTS
- Officials (`officials`): OFFICIAL_ID, FIRST_NAME, LAST_NAME, JERSEY_NUM
- OtherStats (`other_stats`): LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PTS_PAINT, PTS_2ND_CHANCE, PTS_FB, LARGEST_LEAD, LEAD_CHANGES, TIMES_TIED, TEAM_TURNOVERS, TOTAL_TURNOVERS, TEAM_REBOUNDS, PTS_OFF_TO
- SeasonSeries (`season_series`): GAME_ID, HOME_TEAM_ID, VISITOR_TEAM_ID, GAME_DATE_EST, HOME_TEAM_WINS, HOME_TEAM_LOSSES, SERIES_LEADER

## BoxScoreTraditionalV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscoretraditionalv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscoretraditionalv2?EndPeriod=1&EndRange=0&GameID=0021700807&RangeType=0&StartPeriod=1&StartRange=0`

```python
from nba_api.stats.endpoints import boxscoretraditionalv2
endpoint = boxscoretraditionalv2.BoxScoreTraditionalV2(
    end_period=1,
    end_range=0,
    game_id='0021700807',
    range_type=0,
    start_period=1,
    start_range=0,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerStats (`player_stats`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TO, PF, PTS, PLUS_MINUS
- TeamStarterBenchStats (`team_starter_bench_stats`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, STARTERS_BENCH, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TO, PF, PTS
- TeamStats (`team_stats`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TO, PF, PTS, PLUS_MINUS

## BoxScoreUsageV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/boxscoreusagev2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/boxscoreusagev2?EndPeriod=1&EndRange=0&GameID=0021700807&RangeType=0&StartPeriod=1&StartRange=0`

```python
from nba_api.stats.endpoints import boxscoreusagev2
endpoint = boxscoreusagev2.BoxScoreUsageV2(
    end_period=1,
    end_range=0,
    game_id='0021700807',
    range_type=0,
    start_period=1,
    start_range=0,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- sqlPlayersUsage (`sql_players_usage`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MIN, USG_PCT, PCT_FGM, PCT_FGA, PCT_FG3M, PCT_FG3A, PCT_FTM, PCT_FTA, PCT_OREB, PCT_DREB, PCT_REB, PCT_AST, PCT_TOV, PCT_STL, PCT_BLK, PCT_BLKA, PCT_PF, PCT_PFD, PCT_PTS
- sqlTeamsUsage (`sql_teams_usage`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MIN, USG_PCT, PCT_FGM, PCT_FGA, PCT_FG3M, PCT_FG3A, PCT_FTM, PCT_FTA, PCT_OREB, PCT_DREB, PCT_REB, PCT_AST, PCT_TOV, PCT_STL, PCT_BLK, PCT_BLKA, PCT_PF, PCT_PFD, PCT_PTS

## CommonAllPlayers

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/commonallplayers.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/commonallplayers?IsOnlyCurrentSeason=0&LeagueID=00&Season=2019-20`

```python
from nba_api.stats.endpoints import commonallplayers
endpoint = commonallplayers.CommonAllPlayers(
    is_only_current_season=0,
    league_id='00',
    season='2019-20',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- CommonAllPlayers (`common_all_players`): PERSON_ID, DISPLAY_LAST_COMMA_FIRST, DISPLAY_FIRST_LAST, ROSTERSTATUS, FROM_YEAR, TO_YEAR, PLAYERCODE, TEAM_ID, TEAM_CITY, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CODE, GAMES_PLAYED_FLAG, OTHERLEAGUE_EXPERIENCE_CH

## CommonPlayerInfo

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/commonplayerinfo.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/commonplayerinfo?LeagueID=&PlayerID=2544`

```python
from nba_api.stats.endpoints import commonplayerinfo
endpoint = commonplayerinfo.CommonPlayerInfo(
    league_id_nullable="",
    player_id=2544,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AvailableSeasons (`available_seasons`): SEASON_ID
- CommonPlayerInfo (`common_player_info`): PERSON_ID, FIRST_NAME, LAST_NAME, DISPLAY_FIRST_LAST, DISPLAY_LAST_COMMA_FIRST, DISPLAY_FI_LAST, PLAYER_SLUG, BIRTHDATE, SCHOOL, COUNTRY, LAST_AFFILIATION, HEIGHT, WEIGHT, SEASON_EXP, JERSEY, POSITION, ROSTERSTATUS, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CODE, TEAM_CITY, PLAYERCODE, FROM_YEAR, TO_YEAR, DLEAGUE_FLAG, NBA_FLAG, GAMES_PLAYED_FLAG, DRAFT_YEAR, DRAFT_ROUND, DRAFT_NUMBER
- PlayerHeadlineStats (`player_headline_stats`): PLAYER_ID, PLAYER_NAME, TimeFrame, PTS, AST, REB, PIE

## CommonPlayoffSeries

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/commonplayoffseries.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/commonplayoffseries?LeagueID=00&Season=2019-20&SeriesID=`

```python
from nba_api.stats.endpoints import commonplayoffseries
endpoint = commonplayoffseries.CommonPlayoffSeries(
    league_id='00',
    season='2019-20',
    series_id_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayoffSeries (`playoff_series`): GAME_ID, HOME_TEAM_ID, VISITOR_TEAM_ID, SERIES_ID, GAME_NUM

## CommonTeamRoster

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/commonteamroster.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/commonteamroster?LeagueID=&Season=2019-20&TeamID=1610612739`

```python
from nba_api.stats.endpoints import commonteamroster
endpoint = commonteamroster.CommonTeamRoster(
    league_id_nullable="",
    season='2019-20',
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Coaches (`coaches`): TEAM_ID, SEASON, COACH_ID, FIRST_NAME, LAST_NAME, COACH_NAME, IS_ASSISTANT, COACH_TYPE, SORT_SEQUENCE
- CommonTeamRoster (`common_team_roster`): TeamID, SEASON, LeagueID, PLAYER, PLAYER_SLUG, NUM, POSITION, HEIGHT, WEIGHT, BIRTH_DATE, AGE, EXP, SCHOOL, PLAYER_ID

## CommonTeamYears

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/commonteamyears.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/commonteamyears?LeagueID=00`

```python
from nba_api.stats.endpoints import commonteamyears
endpoint = commonteamyears.CommonTeamYears(
    league_id='00',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- TeamYears (`team_years`): LEAGUE_ID, TEAM_ID, MIN_YEAR, MAX_YEAR, ABBREVIATION

## CumeStatsPlayer

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/cumestatsplayer.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/cumestatsplayer?GameIDs=0021700807&LeagueID=00&PlayerID=2544&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import cumestatsplayer
endpoint = cumestatsplayer.CumeStatsPlayer(
    game_ids='0021700807',
    league_id='00',
    player_id=2544,
    season='2019-20',
    season_type_all_star='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- GameByGameStats (`game_by_game_stats`): DATE_EST, VISITOR_TEAM, HOME_TEAM, GP, GS, ACTUAL_MINUTES, ACTUAL_SECONDS, FG, FGA, FG_PCT, FG3, FG3A, FG3_PCT, FT, FTA, FT_PCT, OFF_REB, DEF_REB, TOT_REB, AVG_TOT_REB, AST, PF, DQ, STL, TURNOVERS, BLK, PTS, AVG_PTS
- TotalPlayerStats (`total_player_stats`): DISPLAY_FI_LAST, PERSON_ID, JERSEY_NUM, GP, GS, ACTUAL_MINUTES, ACTUAL_SECONDS, FG, FGA, FG_PCT, FG3, FG3A, FG3_PCT, FT, FTA, FT_PCT, OFF_REB, DEF_REB, TOT_REB, AST, PF, DQ, STL, TURNOVERS, BLK, PTS, MAX_ACTUAL_MINUTES, MAX_ACTUAL_SECONDS, MAX_REB, MAX_AST, MAX_STL, MAX_TURNOVERS, MAX_BLK, MAX_PTS, AVG_ACTUAL_MINUTES, AVG_ACTUAL_SECONDS, AVG_TOT_REB, AVG_AST, AVG_STL, AVG_TURNOVERS, AVG_BLK, AVG_PTS, PER_MIN_TOT_REB, PER_MIN_AST, PER_MIN_STL, PER_MIN_TURNOVERS, PER_MIN_BLK, PER_MIN_PTS

## CumeStatsPlayerGames

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/cumestatsplayergames.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/cumestatsplayergames?LeagueID=00&Location=&Outcome=&PlayerID=2544&Season=2019-20&SeasonType=Regular+Season&VsConference=&VsDivision=&VsTeamID=`

```python
from nba_api.stats.endpoints import cumestatsplayergames
endpoint = cumestatsplayergames.CumeStatsPlayerGames(
    league_id='00',
    location_nullable="",
    outcome_nullable="",
    player_id=2544,
    season='2019-20',
    season_type_all_star='Regular Season',
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_team_id_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- CumeStatsPlayerGames (`cume_stats_player_games`): MATCHUP, GAME_ID

## CumeStatsTeam

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/cumestatsteam.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/cumestatsteam?GameIDs=0021700807&LeagueID=00&Season=2019-20&SeasonType=Regular+Season&TeamID=1610612739`

```python
from nba_api.stats.endpoints import cumestatsteam
endpoint = cumestatsteam.CumeStatsTeam(
    game_ids='0021700807',
    league_id='00',
    season='2019-20',
    season_type_all_star='Regular Season',
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- GameByGameStats (`game_by_game_stats`): JERSEY_NUM, PLAYER, PERSON_ID, TEAM_ID, GP, GS, ACTUAL_MINUTES, ACTUAL_SECONDS, FG, FGA, FG_PCT, FG3, FG3A, FG3_PCT, FT, FTA, FT_PCT, OFF_REB, DEF_REB, TOT_REB, AST, PF, DQ, STL, TURNOVERS, BLK, PTS, MAX_ACTUAL_MINUTES, MAX_ACTUAL_SECONDS, MAX_REB, MAX_AST, MAX_STL, MAX_TURNOVERS, MAX_BLKP, MAX_PTS, AVG_ACTUAL_MINUTES, AVG_ACTUAL_SECONDS, AVG_REB, AVG_AST, AVG_STL, AVG_TURNOVERS, AVG_BLKP, AVG_PTS, PER_MIN_REB, PER_MIN_AST, PER_MIN_STL, PER_MIN_TURNOVERS, PER_MIN_BLK, PER_MIN_PTS
- TotalTeamStats (`total_team_stats`): CITY, NICKNAME, TEAM_ID, W, L, W_HOME, L_HOME, W_ROAD, L_ROAD, TEAM_TURNOVERS, TEAM_REBOUNDS, GP, GS, ACTUAL_MINUTES, ACTUAL_SECONDS, FG, FGA, FG_PCT, FG3, FG3A, FG3_PCT, FT, FTA, FT_PCT, OFF_REB, DEF_REB, TOT_REB, AST, PF, STL, TOTAL_TURNOVERS, BLK, PTS, AVG_REB, AVG_PTS, DQ

## CumeStatsTeamGames

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/cumestatsteamgames.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/cumestatsteamgames?LeagueID=00&Location=&Outcome=&Season=2019-20&SeasonID=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=&VsTeamID=`

```python
from nba_api.stats.endpoints import cumestatsteamgames
endpoint = cumestatsteamgames.CumeStatsTeamGames(
    league_id='00',
    location_nullable="",
    outcome_nullable="",
    season='2019-20',
    season_id_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_team_id_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- CumeStatsTeamGames (`cume_stats_team_games`): MATCHUP, GAME_ID

## DefenseHub

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/defensehub.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/defensehub?GameScope=Season&LeagueID=00&PlayerOrTeam=Team&PlayerScope=All+Players&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import defensehub
endpoint = defensehub.DefenseHub(
    game_scope_detailed='Season',
    league_id='00',
    player_or_team='Team',
    player_scope='All Players',
    season='2019-20',
    season_type_playoffs='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DefenseHubStat1 (`defense_hub_stat1`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, DREB
- DefenseHubStat10 (`defense_hub_stat10`): (empty)
- DefenseHubStat2 (`defense_hub_stat2`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, STL
- DefenseHubStat3 (`defense_hub_stat3`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, BLK
- DefenseHubStat4 (`defense_hub_stat4`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, TM_DEF_RATING
- DefenseHubStat5 (`defense_hub_stat5`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, OVERALL_PM
- DefenseHubStat6 (`defense_hub_stat6`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, THREEP_DFGPCT
- DefenseHubStat7 (`defense_hub_stat7`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, TWOP_DFGPCT
- DefenseHubStat8 (`defense_hub_stat8`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, FIFETEENF_DFGPCT
- DefenseHubStat9 (`defense_hub_stat9`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, DEF_RIM_PCT

## DraftBoard

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/draftboard.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/draftboard?College=&LeagueID=00&OverallPick=&RoundNum=&RoundPick=&Season=2019&TeamID=&TopX=`

```python
from nba_api.stats.endpoints import draftboard
endpoint = draftboard.DraftBoard(
    college_nullable="",
    league_id='00',
    overall_pick_nullable="",
    round_num_nullable="",
    round_pick_nullable="",
    season_year=2019,
    team_id_nullable="",
    topx_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DraftBoard (`draft_board`): PERSON_ID, PLAYER_NAME, SEASON, ROUND_NUMBER, ROUND_PICK, OVERALL_PICK, TEAM_ID, TEAM_CITY, TEAM_NAME, TEAM_ABBREVIATION, ORGANIZATION, ORGANIZATION_TYPE, HEIGHT, WEIGHT, POSITION, JERSEY_NUMBER, BIRTHDATE, AGE

## DraftCombineDrillResults

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/draftcombinedrillresults.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/draftcombinedrillresults?LeagueID=00&SeasonYear=2019`

```python
from nba_api.stats.endpoints import draftcombinedrillresults
endpoint = draftcombinedrillresults.DraftCombineDrillResults(
    league_id='00',
    season_year=2019,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Results (`results`): TEMP_PLAYER_ID, PLAYER_ID, FIRST_NAME, LAST_NAME, PLAYER_NAME, POSITION, STANDING_VERTICAL_LEAP, MAX_VERTICAL_LEAP, LANE_AGILITY_TIME, MODIFIED_LANE_AGILITY_TIME, THREE_QUARTER_SPRINT, BENCH_PRESS

## DraftCombineNonStationaryShooting

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/draftcombinenonstationaryshooting.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/draftcombinenonstationaryshooting?LeagueID=00&SeasonYear=2019`

```python
from nba_api.stats.endpoints import draftcombinenonstationaryshooting
endpoint = draftcombinenonstationaryshooting.DraftCombineNonStationaryShooting(
    league_id='00',
    season_year=2019,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Results (`results`): TEMP_PLAYER_ID, PLAYER_ID, FIRST_NAME, LAST_NAME, PLAYER_NAME, POSITION, OFF_DRIB_FIFTEEN_BREAK_LEFT_MADE, OFF_DRIB_FIFTEEN_BREAK_LEFT_ATTEMPT, OFF_DRIB_FIFTEEN_BREAK_LEFT_PCT, OFF_DRIB_FIFTEEN_TOP_KEY_MADE, OFF_DRIB_FIFTEEN_TOP_KEY_ATTEMPT, OFF_DRIB_FIFTEEN_TOP_KEY_PCT, OFF_DRIB_FIFTEEN_BREAK_RIGHT_MADE, OFF_DRIB_FIFTEEN_BREAK_RIGHT_ATTEMPT, OFF_DRIB_FIFTEEN_BREAK_RIGHT_PCT, OFF_DRIB_COLLEGE_BREAK_LEFT_MADE, OFF_DRIB_COLLEGE_BREAK_LEFT_ATTEMPT, OFF_DRIB_COLLEGE_BREAK_LEFT_PCT, OFF_DRIB_COLLEGE_TOP_KEY_MADE, OFF_DRIB_COLLEGE_TOP_KEY_ATTEMPT, OFF_DRIB_COLLEGE_TOP_KEY_PCT, OFF_DRIB_COLLEGE_BREAK_RIGHT_MADE, OFF_DRIB_COLLEGE_BREAK_RIGHT_ATTEMPT, OFF_DRIB_COLLEGE_BREAK_RIGHT_PCT, ON_MOVE_FIFTEEN_MADE, ON_MOVE_FIFTEEN_ATTEMPT, ON_MOVE_FIFTEEN_PCT, ON_MOVE_COLLEGE_MADE, ON_MOVE_COLLEGE_ATTEMPT, ON_MOVE_COLLEGE_PCT

## DraftCombinePlayerAnthro

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/draftcombineplayeranthro.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/draftcombineplayeranthro?LeagueID=00&SeasonYear=2019`

```python
from nba_api.stats.endpoints import draftcombineplayeranthro
endpoint = draftcombineplayeranthro.DraftCombinePlayerAnthro(
    league_id='00',
    season_year=2019,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Results (`results`): TEMP_PLAYER_ID, PLAYER_ID, FIRST_NAME, LAST_NAME, PLAYER_NAME, POSITION, HEIGHT_WO_SHOES, HEIGHT_WO_SHOES_FT_IN, HEIGHT_W_SHOES, HEIGHT_W_SHOES_FT_IN, WEIGHT, WINGSPAN, WINGSPAN_FT_IN, STANDING_REACH, STANDING_REACH_FT_IN, BODY_FAT_PCT, HAND_LENGTH, HAND_WIDTH

## DraftCombineSpotShooting

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/draftcombinespotshooting.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/draftcombinespotshooting?LeagueID=00&SeasonYear=2019`

```python
from nba_api.stats.endpoints import draftcombinespotshooting
endpoint = draftcombinespotshooting.DraftCombineSpotShooting(
    league_id='00',
    season_year=2019,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Results (`results`): TEMP_PLAYER_ID, PLAYER_ID, FIRST_NAME, LAST_NAME, PLAYER_NAME, POSITION, FIFTEEN_CORNER_LEFT_MADE, FIFTEEN_CORNER_LEFT_ATTEMPT, FIFTEEN_CORNER_LEFT_PCT, FIFTEEN_BREAK_LEFT_MADE, FIFTEEN_BREAK_LEFT_ATTEMPT, FIFTEEN_BREAK_LEFT_PCT, FIFTEEN_TOP_KEY_MADE, FIFTEEN_TOP_KEY_ATTEMPT, FIFTEEN_TOP_KEY_PCT, FIFTEEN_BREAK_RIGHT_MADE, FIFTEEN_BREAK_RIGHT_ATTEMPT, FIFTEEN_BREAK_RIGHT_PCT, FIFTEEN_CORNER_RIGHT_MADE, FIFTEEN_CORNER_RIGHT_ATTEMPT, FIFTEEN_CORNER_RIGHT_PCT, COLLEGE_CORNER_LEFT_MADE, COLLEGE_CORNER_LEFT_ATTEMPT, COLLEGE_CORNER_LEFT_PCT, COLLEGE_BREAK_LEFT_MADE, COLLEGE_BREAK_LEFT_ATTEMPT, COLLEGE_BREAK_LEFT_PCT, COLLEGE_TOP_KEY_MADE, COLLEGE_TOP_KEY_ATTEMPT, COLLEGE_TOP_KEY_PCT, COLLEGE_BREAK_RIGHT_MADE, COLLEGE_BREAK_RIGHT_ATTEMPT, COLLEGE_BREAK_RIGHT_PCT, COLLEGE_CORNER_RIGHT_MADE, COLLEGE_CORNER_RIGHT_ATTEMPT, COLLEGE_CORNER_RIGHT_PCT, NBA_CORNER_LEFT_MADE, NBA_CORNER_LEFT_ATTEMPT, NBA_CORNER_LEFT_PCT, NBA_BREAK_LEFT_MADE, NBA_BREAK_LEFT_ATTEMPT, NBA_BREAK_LEFT_PCT, NBA_TOP_KEY_MADE, NBA_TOP_KEY_ATTEMPT, NBA_TOP_KEY_PCT, NBA_BREAK_RIGHT_MADE, NBA_BREAK_RIGHT_ATTEMPT, NBA_BREAK_RIGHT_PCT, NBA_CORNER_RIGHT_MADE, NBA_CORNER_RIGHT_ATTEMPT, NBA_CORNER_RIGHT_PCT

## DraftCombineStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/draftcombinestats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/draftcombinestats?LeagueID=00&SeasonYear=2019-20`

```python
from nba_api.stats.endpoints import draftcombinestats
endpoint = draftcombinestats.DraftCombineStats(
    league_id='00',
    season_all_time='2019-20',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DraftCombineStats (`draft_combine_stats`): SEASON, PLAYER_ID, FIRST_NAME, LAST_NAME, PLAYER_NAME, POSITION, HEIGHT_WO_SHOES, HEIGHT_WO_SHOES_FT_IN, HEIGHT_W_SHOES, HEIGHT_W_SHOES_FT_IN, WEIGHT, WINGSPAN, WINGSPAN_FT_IN, STANDING_REACH, STANDING_REACH_FT_IN, BODY_FAT_PCT, HAND_LENGTH, HAND_WIDTH, STANDING_VERTICAL_LEAP, MAX_VERTICAL_LEAP, LANE_AGILITY_TIME, MODIFIED_LANE_AGILITY_TIME, THREE_QUARTER_SPRINT, BENCH_PRESS, SPOT_FIFTEEN_CORNER_LEFT, SPOT_FIFTEEN_BREAK_LEFT, SPOT_FIFTEEN_TOP_KEY, SPOT_FIFTEEN_BREAK_RIGHT, SPOT_FIFTEEN_CORNER_RIGHT, SPOT_COLLEGE_CORNER_LEFT, SPOT_COLLEGE_BREAK_LEFT, SPOT_COLLEGE_TOP_KEY, SPOT_COLLEGE_BREAK_RIGHT, SPOT_COLLEGE_CORNER_RIGHT, SPOT_NBA_CORNER_LEFT, SPOT_NBA_BREAK_LEFT, SPOT_NBA_TOP_KEY, SPOT_NBA_BREAK_RIGHT, SPOT_NBA_CORNER_RIGHT, OFF_DRIB_FIFTEEN_BREAK_LEFT, OFF_DRIB_FIFTEEN_TOP_KEY, OFF_DRIB_FIFTEEN_BREAK_RIGHT, OFF_DRIB_COLLEGE_BREAK_LEFT, OFF_DRIB_COLLEGE_TOP_KEY, OFF_DRIB_COLLEGE_BREAK_RIGHT, ON_MOVE_FIFTEEN, ON_MOVE_COLLEGE

## DraftHistory

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/drafthistory.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/drafthistory?College=&LeagueID=00&OverallPick=&RoundNum=&RoundPick=&Season=&TeamID=&TopX=`

```python
from nba_api.stats.endpoints import drafthistory
endpoint = drafthistory.DraftHistory(
    college_nullable="",
    league_id='00',
    overall_pick_nullable="",
    round_num_nullable="",
    round_pick_nullable="",
    season_year_nullable="",
    team_id_nullable="",
    topx_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DraftHistory (`draft_history`): PERSON_ID, PLAYER_NAME, SEASON, ROUND_NUMBER, ROUND_PICK, OVERALL_PICK, DRAFT_TYPE, TEAM_ID, TEAM_CITY, TEAM_NAME, TEAM_ABBREVIATION, ORGANIZATION, ORGANIZATION_TYPE

## FantasyWidget

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/fantasywidget.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/fantasywidget?ActivePlayers=N&DateFrom=&DateTo=&LastNGames=0&LeagueID=00&Location=&Month=&OpponentTeamID=&PORound=&PlayerID=&Position=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=&TodaysOpponent=0&TodaysPlayers=N&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import fantasywidget
endpoint = fantasywidget.FantasyWidget(
    active_players='N',
    date_from_nullable="",
    date_to_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    po_round_nullable="",
    player_id_nullable="",
    position_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id_nullable="",
    todays_opponent=0,
    todays_players='N',
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- FantasyWidgetResult (`fantasy_widget_result`): PLAYER_ID, PLAYER_NAME, PLAYER_POSITION, TEAM_ID, TEAM_ABBREVIATION, GP, MIN, FAN_DUEL_PTS, NBA_FANTASY_PTS, PTS, REB, AST, BLK, STL, TOV, FG3M, FGA, FG_PCT, FTA, FT_PCT

## FranchiseHistory

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/franchisehistory.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/franchisehistory?LeagueID=00`

```python
from nba_api.stats.endpoints import franchisehistory
endpoint = franchisehistory.FranchiseHistory(
    league_id='00',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DefunctTeams (`defunct_teams`): LEAGUE_ID, TEAM_ID, TEAM_CITY, TEAM_NAME, START_YEAR, END_YEAR, YEARS, GAMES, WINS, LOSSES, WIN_PCT, PO_APPEARANCES, DIV_TITLES, CONF_TITLES, LEAGUE_TITLES
- FranchiseHistory (`franchise_history`): LEAGUE_ID, TEAM_ID, TEAM_CITY, TEAM_NAME, START_YEAR, END_YEAR, YEARS, GAMES, WINS, LOSSES, WIN_PCT, PO_APPEARANCES, DIV_TITLES, CONF_TITLES, LEAGUE_TITLES

## FranchiseLeaders

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/franchiseleaders.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/franchiseleaders?LeagueID=&TeamID=1610612739`

```python
from nba_api.stats.endpoints import franchiseleaders
endpoint = franchiseleaders.FranchiseLeaders(
    league_id_nullable="",
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- FranchiseLeaders (`franchise_leaders`): TEAM_ID, PTS, PTS_PERSON_ID, PTS_PLAYER, AST, AST_PERSON_ID, AST_PLAYER, REB, REB_PERSON_ID, REB_PLAYER, BLK, BLK_PERSON_ID, BLK_PLAYER, STL, STL_PERSON_ID, STL_PLAYER

## FranchisePlayers

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/franchiseplayers.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/franchiseplayers?LeagueID=00&PerMode=Totals&SeasonType=Regular+Season&TeamID=1610612739`

```python
from nba_api.stats.endpoints import franchiseplayers
endpoint = franchiseplayers.FranchisePlayers(
    league_id='00',
    per_mode_detailed='Totals',
    season_type_all_star='Regular Season',
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- FranchisePlayers (`franchise_players`): LEAGUE_ID, TEAM_ID, TEAM, PERSON_ID, PLAYER, SEASON_TYPE, ACTIVE_WITH_TEAM, GP, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, PF, STL, TOV, BLK, PTS

## GameRotation

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/gamerotation.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/gamerotation?GameID=0021700807&LeagueID=00`

```python
from nba_api.stats.endpoints import gamerotation
endpoint = gamerotation.GameRotation(
    game_id='0021700807',
    league_id='00',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AwayTeam (`away_team`): GAME_ID, TEAM_ID, TEAM_CITY, TEAM_NAME, PERSON_ID, PLAYER_FIRST, PLAYER_LAST, IN_TIME_REAL, OUT_TIME_REAL, PLAYER_PTS, PT_DIFF, USG_PCT
- HomeTeam (`home_team`): GAME_ID, TEAM_ID, TEAM_CITY, TEAM_NAME, PERSON_ID, PLAYER_FIRST, PLAYER_LAST, IN_TIME_REAL, OUT_TIME_REAL, PLAYER_PTS, PT_DIFF, USG_PCT

## GLAlumBoxScoreSimilarityScore

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/glalumboxscoresimilarityscore.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/glalumboxscoresimilarityscore?Person1Id=202681&Person1LeagueId=00&Person1Season=2019&Person1SeasonType=Regular+Season&Person2Id=203078&Person2LeagueId=00&Person2Season=2019&Person2SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import glalumboxscoresimilarityscore
endpoint = glalumboxscoresimilarityscore.GLAlumBoxScoreSimilarityScore(
    person1_id=202681,
    person1_league_id='00',
    person1_season_year=2019,
    person1_season_type='Regular Season',
    person2_id=203078,
    person2_league_id='00',
    person2_season_year=2019,
    person2_season_type='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- GLeagueAlumBoxScoreSimilarityScores (`g_league_alum_box_score_similarity_scores`): PERSON_2_ID, PERSON_2, TEAM_ID, SIMILARITY_SCORE

## HomePageLeaders

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/homepageleaders.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/homepageleaders?GameScope=Season&LeagueID=00&PlayerOrTeam=Team&PlayerScope=All+Players&Season=2019-20&SeasonType=Regular+Season&StatCategory=Points`

```python
from nba_api.stats.endpoints import homepageleaders
endpoint = homepageleaders.HomePageLeaders(
    game_scope_detailed='Season',
    league_id='00',
    player_or_team='Team',
    player_scope='All Players',
    season='2019-20',
    season_type_playoffs='Regular Season',
    stat_category='Points',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- HomePageLeaders (`home_page_leaders`): RANK, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, PTS, FG_PCT, FG3_PCT, FT_PCT, EFG_PCT, TS_PCT, PTS_PER48
- LeagueAverage (`league_average`): PTS, FG_PCT, FG3_PCT, FT_PCT, EFG_PCT, TS_PCT, PTS_PER48
- LeagueMax (`league_max`): PTS, FG_PCT, FG3_PCT, FT_PCT, EFG_PCT, TS_PCT, PTS_PER48

## HomePageV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/homepagev2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/homepagev2?GameScope=Season&LeagueID=00&PlayerOrTeam=Team&PlayerScope=All+Players&Season=2019-20&SeasonType=Regular+Season&StatType=Traditional`

```python
from nba_api.stats.endpoints import homepagev2
endpoint = homepagev2.HomePageV2(
    game_scope_detailed='Season',
    league_id='00',
    player_or_team='Team',
    player_scope='All Players',
    season='2019-20',
    season_type_playoffs='Regular Season',
    stat_type='Traditional',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- HomePageStat1 (`home_page_stat1`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, PTS
- HomePageStat2 (`home_page_stat2`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, REB
- HomePageStat3 (`home_page_stat3`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, AST
- HomePageStat4 (`home_page_stat4`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, STL
- HomePageStat5 (`home_page_stat5`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, FG_PCT
- HomePageStat6 (`home_page_stat6`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, FT_PCT
- HomePageStat7 (`home_page_stat7`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, FG3_PCT
- HomePageStat8 (`home_page_stat8`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, BLK

## HustleStatsBoxScore

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/hustlestatsboxscore.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/hustlestatsboxscore?GameID=0021700807`

```python
from nba_api.stats.endpoints import hustlestatsboxscore
endpoint = hustlestatsboxscore.HustleStatsBoxScore(
    game_id='0021700807',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- HustleStatsAvailable (`hustle_stats_available`): GAME_ID, HUSTLE_STATUS
- PlayerStats (`player_stats`): GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, START_POSITION, COMMENT, MINUTES, PTS, CONTESTED_SHOTS, CONTESTED_SHOTS_2PT, CONTESTED_SHOTS_3PT, DEFLECTIONS, CHARGES_DRAWN, SCREEN_ASSISTS, SCREEN_AST_PTS, OFF_LOOSE_BALLS_RECOVERED, DEF_LOOSE_BALLS_RECOVERED, LOOSE_BALLS_RECOVERED, OFF_BOXOUTS, DEF_BOXOUTS, BOX_OUT_PLAYER_TEAM_REBS, BOX_OUT_PLAYER_REBS, BOX_OUTS
- TeamStats (`team_stats`): GAME_ID, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CITY, MINUTES, PTS, CONTESTED_SHOTS, CONTESTED_SHOTS_2PT, CONTESTED_SHOTS_3PT, DEFLECTIONS, CHARGES_DRAWN, SCREEN_ASSISTS, SCREEN_AST_PTS, OFF_LOOSE_BALLS_RECOVERED, DEF_LOOSE_BALLS_RECOVERED, LOOSE_BALLS_RECOVERED, OFF_BOXOUTS, DEF_BOXOUTS, BOX_OUT_PLAYER_TEAM_REBS, BOX_OUT_PLAYER_REBS, BOX_OUTS

## InfographicFanDuelPlayer

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/infographicfanduelplayer.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/infographicfanduelplayer?GameID=0021700807`

```python
from nba_api.stats.endpoints import infographicfanduelplayer
endpoint = infographicfanduelplayer.InfographicFanDuelPlayer(
    game_id='0021700807',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- FanDuelPlayer (`fan_duel_player`): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, JERSEY_NUM, PLAYER_POSITION, LOCATION, FAN_DUEL_PTS, NBA_FANTASY_PTS, USG_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS

## LeadersTiles

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaderstiles.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaderstiles?GameScope=Season&LeagueID=00&PlayerOrTeam=Team&PlayerScope=All+Players&Season=2019-20&SeasonType=Regular+Season&Stat=PTS`

```python
from nba_api.stats.endpoints import leaderstiles
endpoint = leaderstiles.LeadersTiles(
    game_scope_detailed='Season',
    league_id='00',
    player_or_team='Team',
    player_scope='All Players',
    season='2019-20',
    season_type_playoffs='Regular Season',
    stat='PTS',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AllTimeSeasonHigh (`all_time_season_high`): TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, SEASON_YEAR, PTS
- LastSeasonHigh (`last_season_high`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, PTS
- LeadersTiles (`leaders_tiles`): RANK, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, PTS
- LowSeasonHigh (`low_season_high`): TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, SEASON_YEAR, PTS

## LeagueDashLineups

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashlineups.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashlineups?Conference=&DateFrom=&DateTo=&Division=&GameSegment=&GroupQuantity=5&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashlineups
endpoint = leaguedashlineups.LeagueDashLineups(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    game_segment_nullable="",
    group_quantity=5,
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Lineups (`lineups`): GROUP_SET, GROUP_ID, GROUP_NAME, TEAM_ID, TEAM_ABBREVIATION, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK

## LeagueDashPlayerBioStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashplayerbiostats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashplayerbiostats?College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&GameScope=&GameSegment=&Height=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&Period=&PlayerExperience=&PlayerPosition=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashplayerbiostats
endpoint = leaguedashplayerbiostats.LeagueDashPlayerBioStats(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    height_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    period_nullable="",
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPlayerBioStats (`league_dash_player_bio_stats`): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, AGE, PLAYER_HEIGHT, PLAYER_HEIGHT_INCHES, PLAYER_WEIGHT, COLLEGE, COUNTRY, DRAFT_YEAR, DRAFT_ROUND, DRAFT_NUMBER, GP, PTS, REB, AST, NET_RATING, OREB_PCT, DREB_PCT, USG_PCT, TS_PCT, AST_PCT

## LeagueDashPlayerClutch

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashplayerclutch.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashplayerclutch?AheadBehind=Ahead+or+Behind&ClutchTime=Last+5+Minutes&College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&GameScope=&GameSegment=&Height=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerExperience=&PlayerPosition=&PlusMinus=N&PointDiff=5&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashplayerclutch
endpoint = leaguedashplayerclutch.LeagueDashPlayerClutch(
    ahead_behind='Ahead or Behind',
    clutch_time='Last 5 Minutes',
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    height_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    plus_minus='N',
    point_diff=5,
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPlayerClutch (`league_dash_player_clutch`): GROUP_SET, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, AGE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## LeagueDashOppPtShot

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashoppptshot.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashoppptshot?CloseDefDistRange=&Conference=&DateFrom=&DateTo=&Division=&DribbleRange=&GameSegment=&GeneralRange=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&Period=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&ShotDistRange=&TeamID=&TouchTimeRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashoppptshot
endpoint = leaguedashoppptshot.LeagueDashOppPtShot(
    close_def_dist_range_nullable="",
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_nullable="",
    dribble_range_nullable="",
    game_segment_nullable="",
    general_range_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    period_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    shot_dist_range_nullable="",
    team_id_nullable="",
    touch_time_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPTShots (`league_dash_ptshots`): TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, GP, G, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT

## LeagueDashPlayerPtShot

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashplayerptshot.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashplayerptshot?CloseDefDistRange=&College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&DribbleRange=&GameSegment=&GeneralRange=&Height=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&Period=&PlayerExperience=&PlayerPosition=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&ShotDistRange=&StarterBench=&TeamID=&TouchTimeRange=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashplayerptshot
endpoint = leaguedashplayerptshot.LeagueDashPlayerPtShot(
    close_def_dist_range_nullable="",
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    dribble_range_nullable="",
    game_segment_nullable="",
    general_range_nullable="",
    height_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    period_nullable="",
    player_experience_nullable="",
    player_position_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    shot_dist_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    touch_time_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPTShots (`league_dash_ptshots`): PLAYER_ID, PLAYER_NAME, PLAYER_LAST_TEAM_ID, PLAYER_LAST_TEAM_ABBREVIATION, AGE, GP, G, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT

## LeagueDashPlayerShotLocations

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashplayershotlocations.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashplayershotlocations?College=&Conference=&Country=&DateFrom=&DateTo=&DistanceRange=By+Zone&Division=&DraftPick=&DraftYear=&GameScope=&GameSegment=&Height=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerExperience=&PlayerPosition=&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashplayershotlocations
endpoint = leaguedashplayershotlocations.LeagueDashPlayerShotLocations(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    distance_range='By Zone',
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    height_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_simple='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ShotLocations (`shot_locations`): {"columnNames": ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3", "Right Corner 3", "Above the Break 3", "Backcourt"], "columnSpan": 3, "columnsToSkip": 5, "name": "SHOT_CATEGORY"}, {"columnNames": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT"], "columnSpan": 1, "name": "columns"}

## LeagueDashPlayerStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashplayerstats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashplayerstats?College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&GameScope=&GameSegment=&Height=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerExperience=&PlayerPosition=&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&TwoWay=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashplayerstats
endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    height_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    two_way_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPlayerStats (`league_dash_player_stats`): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, AGE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## LeagueDashPtDefend

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashptdefend.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashptdefend?College=&Conference=&Country=&DateFrom=&DateTo=&DefenseCategory=Overall&Division=&DraftPick=&DraftYear=&GameSegment=&Height=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&Period=&PlayerExperience=&PlayerID=&PlayerPosition=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&StarterBench=&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashptdefend
endpoint = leaguedashptdefend.LeagueDashPtDefend(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    defense_category='Overall',
    division_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_segment_nullable="",
    height_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    period_nullable="",
    player_experience_nullable="",
    player_id_nullable="",
    player_position_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPTDefend (`league_dash_p_tdefend`): CLOSE_DEF_PERSON_ID, PLAYER_NAME, PLAYER_LAST_TEAM_ID, PLAYER_LAST_TEAM_ABBREVIATION, PLAYER_POSITION, AGE, GP, G, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, PCT_PLUSMINUS

## LeagueDashPtStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashptstats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashptstats?College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&GameScope=&Height=&LastNGames=0&LeagueID=&Location=&Month=0&OpponentTeamID=0&Outcome=&PORound=&PerMode=Totals&PlayerExperience=&PlayerOrTeam=Team&PlayerPosition=&PtMeasureType=SpeedDistance&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&StarterBench=&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguedashptstats
endpoint = leaguedashptstats.LeagueDashPtStats(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    game_scope_simple_nullable="",
    height_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    player_experience_nullable="",
    player_or_team='Team',
    player_position_abbreviation_nullable="",
    pt_measure_type='SpeedDistance',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPtStats (`league_dash_pt_stats`): TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GP, W, L, MIN, DIST_FEET, DIST_MILES, DIST_MILES_OFF, DIST_MILES_DEF, AVG_SPEED, AVG_SPEED_OFF, AVG_SPEED_DEF

## LeagueDashPtTeamDefend

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashptteamdefend.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashptteamdefend?Conference=&DateFrom=&DateTo=&DefenseCategory=Overall&Division=&GameSegment=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&Period=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashptteamdefend
endpoint = leaguedashptteamdefend.LeagueDashPtTeamDefend(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    defense_category='Overall',
    division_nullable="",
    game_segment_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    period_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPtTeamDefend (`league_dash_pt_team_defend`): TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, GP, G, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, PCT_PLUSMINUS

## LeagueDashTeamClutch

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashteamclutch.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashteamclutch?AheadBehind=Ahead+or+Behind&ClutchTime=Last+5+Minutes&Conference=&DateFrom=&DateTo=&Division=&GameScope=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerExperience=&PlayerPosition=&PlusMinus=N&PointDiff=5&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashteamclutch
endpoint = leaguedashteamclutch.LeagueDashTeamClutch(
    ahead_behind='Ahead or Behind',
    clutch_time='Last 5 Minutes',
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    plus_minus='N',
    point_diff=5,
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashTeamClutch (`league_dash_team_clutch`): TEAM_ID, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS

## LeagueDashTeamPtShot

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashteamptshot.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashteamptshot?CloseDefDistRange=&Conference=&DateFrom=&DateTo=&Division=&DribbleRange=&GameSegment=&GeneralRange=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&Period=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&ShotDistRange=&TeamID=&TouchTimeRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashteamptshot
endpoint = leaguedashteamptshot.LeagueDashTeamPtShot(
    close_def_dist_range_nullable="",
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_nullable="",
    dribble_range_nullable="",
    game_segment_nullable="",
    general_range_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple='Totals',
    period_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    shot_dist_range_nullable="",
    team_id_nullable="",
    touch_time_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashPTShots (`league_dash_ptshots`): TEAM_ID, TEAM_NAME, TEAM_ABBREVIATION, GP, G, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT

## LeagueDashTeamShotLocations

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashteamshotlocations.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashteamshotlocations?Conference=&DateFrom=&DateTo=&DistanceRange=By+Zone&Division=&GameScope=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerExperience=&PlayerPosition=&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashteamshotlocations
endpoint = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    distance_range='By Zone',
    division_simple_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_simple='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ShotLocations (`shot_locations`): {"columnNames": ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3", "Right Corner 3", "Above the Break 3", "Backcourt"], "columnSpan": 3, "columnsToSkip": 2, "name": "SHOT_CATEGORY"}, {"columnNames": ["TEAM_ID", "TEAM_NAME", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT", "FGM", "FGA", "FG_PCT"], "columnSpan": 1, "name": "columns"}

## LeagueDashTeamStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguedashteamstats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguedashteamstats?Conference=&DateFrom=&DateTo=&Division=&GameScope=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerExperience=&PlayerPosition=&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&StarterBench=&TeamID=&TwoWay=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguedashteamstats
endpoint = leaguedashteamstats.LeagueDashTeamStats(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    game_scope_simple_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_experience_nullable="",
    player_position_abbreviation_nullable="",
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    two_way_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueDashTeamStats (`league_dash_team_stats`): TEAM_ID, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS

## LeagueHustleStatsPlayer

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguehustlestatsplayer.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguehustlestatsplayer?College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&Height=&LeagueID=&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&PlayerExperience=&PlayerPosition=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguehustlestatsplayer
endpoint = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    height_nullable="",
    league_id_nullable="",
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_time='Totals',
    player_experience_nullable="",
    player_position_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- HustleStatsPlayer (`hustle_stats_player`): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, AGE, G, MIN, CONTESTED_SHOTS, CONTESTED_SHOTS_2PT, CONTESTED_SHOTS_3PT, DEFLECTIONS, CHARGES_DRAWN, SCREEN_ASSISTS, SCREEN_AST_PTS, OFF_LOOSE_BALLS_RECOVERED, DEF_LOOSE_BALLS_RECOVERED, LOOSE_BALLS_RECOVERED, PCT_LOOSE_BALLS_RECOVERED_OFF, PCT_LOOSE_BALLS_RECOVERED_DEF, OFF_BOXOUTS, DEF_BOXOUTS, BOX_OUT_PLAYER_TEAM_REBS, BOX_OUT_PLAYER_REBS, BOX_OUTS, PCT_BOX_OUTS_OFF, PCT_BOX_OUTS_DEF, PCT_BOX_OUTS_TEAM_REB, PCT_BOX_OUTS_REB

## LeagueHustleStatsTeam

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguehustlestatsteam.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguehustlestatsteam?College=&Conference=&Country=&DateFrom=&DateTo=&Division=&DraftPick=&DraftYear=&Height=&LeagueID=&Location=&Month=&OpponentTeamID=&Outcome=&PORound=&PerMode=Totals&PlayerExperience=&PlayerPosition=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=&VsConference=&VsDivision=&Weight=`

```python
from nba_api.stats.endpoints import leaguehustlestatsteam
endpoint = leaguehustlestatsteam.LeagueHustleStatsTeam(
    college_nullable="",
    conference_nullable="",
    country_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_pick_nullable="",
    draft_year_nullable="",
    height_nullable="",
    league_id_nullable="",
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_time='Totals',
    player_experience_nullable="",
    player_position_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    weight_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- HustleStatsTeam (`hustle_stats_team`): TEAM_ID, TEAM_NAME, MIN, CONTESTED_SHOTS, CONTESTED_SHOTS_2PT, CONTESTED_SHOTS_3PT, DEFLECTIONS, CHARGES_DRAWN, SCREEN_ASSISTS, SCREEN_AST_PTS, OFF_LOOSE_BALLS_RECOVERED, DEF_LOOSE_BALLS_RECOVERED, LOOSE_BALLS_RECOVERED, PCT_LOOSE_BALLS_RECOVERED_OFF, PCT_LOOSE_BALLS_RECOVERED_DEF, OFF_BOXOUTS, DEF_BOXOUTS, BOX_OUTS, PCT_BOX_OUTS_OFF, PCT_BOX_OUTS_DEF

## LeagueGameFinder

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguegamefinder.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguegamefinder?Conference=&DateFrom=&DateTo=&Division=&DraftNumber=&DraftRound=&DraftTeamID=&DraftYear=&EqAST=&EqBLK=&EqDD=&EqDREB=&EqFG3A=&EqFG3M=&EqFG3_PCT=&EqFGA=&EqFGM=&EqFG_PCT=&EqFTA=&EqFTM=&EqFT_PCT=&EqMINUTES=&EqOREB=&EqPF=&EqPTS=&EqREB=&EqSTL=&EqTD=&EqTOV=&GameID=&GtAST=&GtBLK=&GtDD=&GtDREB=&GtFG3A=&GtFG3M=&GtFG3_PCT=&GtFGA=&GtFGM=&GtFG_PCT=&GtFTA=&GtFTM=&GtFT_PCT=&GtMINUTES=&GtOREB=&GtPF=&GtPTS=&GtREB=&GtSTL=&GtTD=&GtTOV=&LeagueID=&Location=&LtAST=&LtBLK=&LtDD=&LtDREB=&LtFG3A=&LtFG3M=&LtFG3_PCT=&LtFGA=&LtFGM=&LtFG_PCT=&LtFTA=&LtFTM=&LtFT_PCT=&LtMINUTES=&LtOREB=&LtPF=&LtPTS=&LtREB=&LtSTL=&LtTD=&LtTOV=&Outcome=&PORound=&PlayerID=&PlayerOrTeam=T&RookieYear=&Season=&SeasonSegment=&SeasonType=&StarterBench=&TeamID=&VsConference=&VsDivision=&VsTeamID=&YearsExperience=`

```python
from nba_api.stats.endpoints import leaguegamefinder
endpoint = leaguegamefinder.LeagueGameFinder(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_number_nullable="",
    draft_round_nullable="",
    draft_team_id_nullable="",
    draft_year_nullable="",
    eq_ast_nullable="",
    eq_blk_nullable="",
    eq_dd_nullable="",
    eq_dreb_nullable="",
    eq_fg3a_nullable="",
    eq_fg3m_nullable="",
    eq_fga_nullable="",
    eq_fgm_nullable="",
    eq_fta_nullable="",
    eq_ftm_nullable="",
    eq_minutes_nullable="",
    eq_oreb_nullable="",
    eq_pf_nullable="",
    eq_pts_nullable="",
    eq_reb_nullable="",
    eq_stl_nullable="",
    eq_td_nullable="",
    eq_tov_nullable="",
    game_id_nullable="",
    gt_ast_nullable="",
    gt_blk_nullable="",
    gt_dd_nullable="",
    gt_dreb_nullable="",
    gt_fg3a_nullable="",
    gt_fg3m_nullable="",
    gt_fga_nullable="",
    gt_fgm_nullable="",
    gt_fta_nullable="",
    gt_ftm_nullable="",
    gt_minutes_nullable="",
    gt_oreb_nullable="",
    gt_pf_nullable="",
    gt_pts_nullable="",
    gt_reb_nullable="",
    gt_stl_nullable="",
    gt_td_nullable="",
    gt_tov_nullable="",
    league_id_nullable="",
    location_nullable="",
    lt_ast_nullable="",
    lt_blk_nullable="",
    lt_dd_nullable="",
    lt_dreb_nullable="",
    lt_fg3a_nullable="",
    lt_fg3m_nullable="",
    lt_fga_nullable="",
    lt_fgm_nullable="",
    lt_fta_nullable="",
    lt_ftm_nullable="",
    lt_minutes_nullable="",
    lt_oreb_nullable="",
    lt_pf_nullable="",
    lt_pts_nullable="",
    lt_reb_nullable="",
    lt_stl_nullable="",
    lt_td_nullable="",
    lt_tov_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    player_id_nullable="",
    player_or_team_abbreviation='T',
    rookie_year_nullable="",
    season_nullable="",
    season_segment_nullable="",
    season_type_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_team_id_nullable="",
    years_experience_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueGameFinderResults (`league_game_finder_results`): SEASON_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GAME_ID, GAME_DATE, MATCHUP, WL, MIN, PTS, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PLUS_MINUS

## LeagueGameLog

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguegamelog.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguegamelog?Counter=0&DateFrom=&DateTo=&Direction=ASC&LeagueID=00&PlayerOrTeam=T&Season=2019-20&SeasonType=Regular+Season&Sorter=DATE`

```python
from nba_api.stats.endpoints import leaguegamelog
endpoint = leaguegamelog.LeagueGameLog(
    counter=0,
    date_from_nullable="",
    date_to_nullable="",
    direction='ASC',
    league_id='00',
    player_or_team_abbreviation='T',
    season='2019-20',
    season_type_all_star='Regular Season',
    sorter='DATE',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueGameLog (`league_game_log`): SEASON_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GAME_ID, GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS, PLUS_MINUS, VIDEO_AVAILABLE

## LeagueLeaders

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leagueleaders.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leagueleaders?ActiveFlag=&LeagueID=00&PerMode=Totals&Scope=S&Season=2019-20&SeasonType=Regular+Season&StatCategory=PTS`

```python
from nba_api.stats.endpoints import leagueleaders
endpoint = leagueleaders.LeagueLeaders(
    active_flag_nullable="",
    league_id='00',
    per_mode48='Totals',
    scope='S',
    season='2019-20',
    season_type_all_star='Regular Season',
    stat_category_abbreviation='PTS',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueLeaders (`league_leaders`): PLAYER_ID, RANK, PLAYER, TEAM, GP, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS, EFF, AST_TOV, STL_TOV

## LeagueLineupViz

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguelineupviz.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguelineupviz?Conference=&DateFrom=&DateTo=&Division=&GameSegment=&GroupQuantity=5&LastNGames=0&LeagueID=&Location=&MeasureType=Base&MinutesMin=10&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leaguelineupviz
endpoint = leaguelineupviz.LeagueLineupViz(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    game_segment_nullable="",
    group_quantity=5,
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    minutes_min=10,
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueLineupViz (`league_lineup_viz`): GROUP_ID, GROUP_NAME, TEAM_ID, TEAM_ABBREVIATION, MIN, OFF_RATING, DEF_RATING, NET_RATING, PACE, TS_PCT, FTA_RATE, TM_AST_PCT, PCT_FGA_2PT, PCT_FGA_3PT, PCT_PTS_2PT_MR, PCT_PTS_FB, PCT_PTS_FT, PCT_PTS_PAINT, PCT_AST_FGM, PCT_UAST_FGM, OPP_FG3_PCT, OPP_EFG_PCT, OPP_FTA_RATE, OPP_TOV_PCT

## LeaguePlayerOnDetails

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leagueplayerondetails.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leagueplayerondetails?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import leagueplayerondetails
endpoint = leagueplayerondetails.LeaguePlayerOnDetails(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayersOnCourtLeaguePlayerDetails (`players_on_court_league_player_details`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK

## LeagueSeasonMatchups

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leagueseasonmatchups.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leagueseasonmatchups?DefPlayerID=&DefTeamID=&LeagueID=00&OffPlayerID=&OffTeamID=&PerMode=Totals&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import leagueseasonmatchups
endpoint = leagueseasonmatchups.LeagueSeasonMatchups(
    def_player_id_nullable="",
    def_team_id_nullable="",
    league_id='00',
    off_player_id_nullable="",
    off_team_id_nullable="",
    per_mode_simple='Totals',
    season='2019-20',
    season_type_playoffs='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- SeasonMatchups (`season_matchups`): SEASON_ID, OFF_PLAYER_ID, OFF_PLAYER_NAME, DEF_PLAYER_ID, DEF_PLAYER_NAME, GP, MATCHUP_MIN, PARTIAL_POSS, PLAYER_PTS, TEAM_PTS, MATCHUP_AST, MATCHUP_TOV, MATCHUP_BLK, MATCHUP_FGM, MATCHUP_FGA, MATCHUP_FG_PCT, MATCHUP_FG3M, MATCHUP_FG3A, MATCHUP_FG3_PCT, HELP_BLK, HELP_FGM, HELP_FGA, HELP_FG_PERC, MATCHUP_FTM, MATCHUP_FTA, SFL

## LeagueStandings

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguestandings.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguestandings?LeagueID=00&Season=2019-20&SeasonType=Regular+Season&SeasonYear=`

```python
from nba_api.stats.endpoints import leaguestandings
endpoint = leaguestandings.LeagueStandings(
    league_id='00',
    season='2019-20',
    season_type='Regular Season',
    season_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Standings (`standings`): LeagueID, SeasonID, TeamID, TeamCity, TeamName, Conference, ConferenceRecord, PlayoffRank, ClinchIndicator, Division, DivisionRecord, DivisionRank, WINS, LOSSES, WinPCT, LeagueRank, Record, HOME, ROAD, L10, Last10Home, Last10Road, OT, ThreePTSOrLess, TenPTSOrMore, LongHomeStreak, strLongHomeStreak, LongRoadStreak, strLongRoadStreak, LongWinStreak, LongLossStreak, CurrentHomeStreak, strCurrentHomeStreak, CurrentRoadStreak, strCurrentRoadStreak, CurrentStreak, strCurrentStreak, ConferenceGamesBack, DivisionGamesBack, ClinchedConferenceTitle, ClinchedDivisionTitle, ClinchedPlayoffBirth, EliminatedConference, EliminatedDivision, AheadAtHalf, BehindAtHalf, TiedAtHalf, AheadAtThird, BehindAtThird, TiedAtThird, Score100PTS, OppScore100PTS, OppOver500, LeadInFGPCT, LeadInReb, FewerTurnovers, PointsPG, OppPointsPG, DiffPointsPG, vsEast, vsAtlantic, vsCentral, vsSoutheast, vsWest, vsNorthwest, vsPacific, vsSouthwest, Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, PreAS, PostAS

## LeagueStandingsV3

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/leaguestandingsv3.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/leaguestandingsv3?LeagueID=00&Season=2019-20&SeasonType=Regular+Season&SeasonYear=`

```python
from nba_api.stats.endpoints import leaguestandingsv3
endpoint = leaguestandingsv3.LeagueStandingsV3(
    league_id='00',
    season='2019-20',
    season_type='Regular Season',
    season_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Standings (`standings`): LeagueID, SeasonID, TeamID, TeamCity, TeamName, TeamSlug, Conference, ConferenceRecord, PlayoffRank, ClinchIndicator, Division, DivisionRecord, DivisionRank, WINS, LOSSES, WinPCT, LeagueRank, Record, HOME, ROAD, L10, Last10Home, Last10Road, OT, ThreePTSOrLess, TenPTSOrMore, LongHomeStreak, strLongHomeStreak, LongRoadStreak, strLongRoadStreak, LongWinStreak, LongLossStreak, CurrentHomeStreak, strCurrentHomeStreak, CurrentRoadStreak, strCurrentRoadStreak, CurrentStreak, strCurrentStreak, ConferenceGamesBack, DivisionGamesBack, ClinchedConferenceTitle, ClinchedDivisionTitle, ClinchedPlayoffBirth, EliminatedConference, EliminatedDivision, AheadAtHalf, BehindAtHalf, TiedAtHalf, AheadAtThird, BehindAtThird, TiedAtThird, Score100PTS, OppScore100PTS, OppOver500, LeadInFGPCT, LeadInReb, FewerTurnovers, PointsPG, OppPointsPG, DiffPointsPG, vsEast, vsAtlantic, vsCentral, vsSoutheast, vsWest, vsNorthwest, vsPacific, vsSouthwest, Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, ReturnToPlay_East_PI_Flag, ReturnToPlay_West_PI_Flag, ReturnToPlay_Already_Eliminated, Seeding_Game_1_Outcome, Seeding_Game_2_Outcome, Seeding_Game_3_Outcome, Seeding_Game_4_Outcome, Seeding_Game_5_Outcome, Seeding_Game_6_Outcome, Seeding_Game_7_Outcome, Seeding_Game_8_Outcome, Seeding_Game_1_ID, Seeding_Game_2_ID, Seeding_Game_3_ID, Seeding_Game_4_ID, Seeding_Game_5_ID, Seeding_Game_6_ID, Seeding_Game_7_ID, Seeding_Game_8_ID, Seeding_Game_1_Opponent, Seeding_Game_2_Opponent, Seeding_Game_3_Opponent, Seeding_Game_4_Opponent, Seeding_Game_5_Opponent, Seeding_Game_6_Opponent, Seeding_Game_7_Opponent, Seeding_Game_8_Opponent, Seeding_Game_1_Label, Seeding_Game_2_Label, Seeding_Game_3_Label, Seeding_Game_4_Label, Seeding_Game_5_Label, Seeding_Game_6_Label, Seeding_Game_7_Label, Seeding_Game_8_Label

## MatchupsRollup

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/matchupsrollup.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/matchupsrollup?DefPlayerID=&DefTeamID=&LeagueID=00&OffPlayerID=&OffTeamID=&PerMode=Totals&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import matchupsrollup
endpoint = matchupsrollup.MatchupsRollup(
    def_player_id_nullable="",
    def_team_id_nullable="",
    league_id='00',
    off_player_id_nullable="",
    off_team_id_nullable="",
    per_mode_simple='Totals',
    season='2019-20',
    season_type_playoffs='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- MatchupsRollup (`matchups_rollup`): SEASON_ID, POSITION, PERCENT_OF_TIME, DEF_PLAYER_ID, DEF_PLAYER_NAME, GP, MATCHUP_MIN, PARTIAL_POSS, PLAYER_PTS, TEAM_PTS, MATCHUP_AST, MATCHUP_TOV, MATCHUP_BLK, MATCHUP_FGM, MATCHUP_FGA, MATCHUP_FG_PCT, MATCHUP_FG3M, MATCHUP_FG3A, MATCHUP_FG3_PCT, MATCHUP_FTM, MATCHUP_FTA, SFL

## Odds

- Doc: `api_docs/nba_api_docs/docs/nba_api/live/endpoints/odds.md`
- API family: `live`

```python
from nba_api.live.nba.endpoints import odds
endpoint = odds.Odds()
response = endpoint.get_dict()
print(type(response).__name__)
print(response.keys())
```

Documented response structure:

- Games (`games`): gameId, sr_id, srMatchId, homeTeamId, awayTeamId, markets
- Markets (`markets`): name, odds_type_id, group_name, books
- Books (`books`): id, name, outcomes, url, countryCode
- Outcomes (`outcomes`): odds_field_id, type, odds, opening_odds, odds_trend, spread, opening_spread

## PlayByPlay

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playbyplay.md`
- API family: `stats`
- Note: Live PlayByPlay docs also exist.
- Valid URL: `https://stats.nba.com/stats/playbyplay?EndPeriod=1&GameID=0021700807&StartPeriod=1`

```python
from nba_api.stats.endpoints import playbyplay
endpoint = playbyplay.PlayByPlay(
    end_period=1,
    game_id='0021700807',
    start_period=1,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AvailableVideo (`available_video`): VIDEO_AVAILABLE_FLAG
- PlayByPlay (`play_by_play`): GAME_ID, EVENTNUM, EVENTMSGTYPE, EVENTMSGACTIONTYPE, PERIOD, WCTIMESTRING, PCTIMESTRING, HOMEDESCRIPTION, NEUTRALDESCRIPTION, VISITORDESCRIPTION, SCORE, SCOREMARGIN

## PlayByPlayV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playbyplayv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playbyplayv2?EndPeriod=1&GameID=0021700807&StartPeriod=1`

```python
from nba_api.stats.endpoints import playbyplayv2
endpoint = playbyplayv2.PlayByPlayV2(
    end_period=1,
    game_id='0021700807',
    start_period=1,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AvailableVideo (`available_video`): VIDEO_AVAILABLE_FLAG
- PlayByPlay (`play_by_play`): GAME_ID, EVENTNUM, EVENTMSGTYPE, EVENTMSGACTIONTYPE, PERIOD, WCTIMESTRING, PCTIMESTRING, HOMEDESCRIPTION, NEUTRALDESCRIPTION, VISITORDESCRIPTION, SCORE, SCOREMARGIN, PERSON1TYPE, PLAYER1_ID, PLAYER1_NAME, PLAYER1_TEAM_ID, PLAYER1_TEAM_CITY, PLAYER1_TEAM_NICKNAME, PLAYER1_TEAM_ABBREVIATION, PERSON2TYPE, PLAYER2_ID, PLAYER2_NAME, PLAYER2_TEAM_ID, PLAYER2_TEAM_CITY, PLAYER2_TEAM_NICKNAME, PLAYER2_TEAM_ABBREVIATION, PERSON3TYPE, PLAYER3_ID, PLAYER3_NAME, PLAYER3_TEAM_ID, PLAYER3_TEAM_CITY, PLAYER3_TEAM_NICKNAME, PLAYER3_TEAM_ABBREVIATION, VIDEO_AVAILABLE_FLAG

## PlayerAwards

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerawards.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerawards?PlayerID=2544`

```python
from nba_api.stats.endpoints import playerawards
endpoint = playerawards.PlayerAwards(
    player_id=2544,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerAwards (`player_awards`): PERSON_ID, FIRST_NAME, LAST_NAME, TEAM, DESCRIPTION, ALL_NBA_TEAM_NUMBER, SEASON, MONTH, WEEK, CONFERENCE, TYPE, SUBTYPE1, SUBTYPE2, SUBTYPE3

## PlayerCareerByCollege

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playercareerbycollege.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playercareerbycollege?College=Ohio+State&LeagueID=00&PerMode=Totals&Season=&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import playercareerbycollege
endpoint = playercareerbycollege.PlayerCareerByCollege(
    college='Ohio State',
    league_id='00',
    per_mode_simple='Totals',
    season_nullable="",
    season_type_all_star='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerCareerByCollege (`player_career_by_college`): PLAYER_ID, PLAYER_NAME, COLLEGE, GP, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS

## PlayerCareerByCollegeRollup

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playercareerbycollegerollup.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playercareerbycollegerollup?LeagueID=00&PerMode=Totals&Season=&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import playercareerbycollegerollup
endpoint = playercareerbycollegerollup.PlayerCareerByCollegeRollup(
    league_id='00',
    per_mode_simple='Totals',
    season_nullable="",
    season_type_all_star='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- East (`east`): REGION, SEED, COLLEGE, PLAYERS, GP, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- Midwest (`midwest`): REGION, SEED, COLLEGE, PLAYERS, GP, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- South (`south`): REGION, SEED, COLLEGE, PLAYERS, GP, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- West (`west`): REGION, SEED, COLLEGE, PLAYERS, GP, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS

## PlayerCareerStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playercareerstats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playercareerstats?LeagueID=&PerMode=Totals&PlayerID=2544`

```python
from nba_api.stats.endpoints import playercareerstats
endpoint = playercareerstats.PlayerCareerStats(
    league_id_nullable="",
    per_mode36='Totals',
    player_id=2544,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- CareerTotalsAllStarSeason (`career_totals_all_star_season`): PLAYER_ID, LEAGUE_ID, Team_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsCollegeSeason (`career_totals_college_season`): PLAYER_ID, LEAGUE_ID, ORGANIZATION_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsPostSeason (`career_totals_post_season`): PLAYER_ID, LEAGUE_ID, Team_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsRegularSeason (`career_totals_regular_season`): PLAYER_ID, LEAGUE_ID, Team_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonRankingsPostSeason (`season_rankings_post_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, RANK_MIN, RANK_FGM, RANK_FGA, RANK_FG_PCT, RANK_FG3M, RANK_FG3A, RANK_FG3_PCT, RANK_FTM, RANK_FTA, RANK_FT_PCT, RANK_OREB, RANK_DREB, RANK_REB, RANK_AST, RANK_STL, RANK_BLK, RANK_TOV, RANK_PTS, RANK_EFF
- SeasonRankingsRegularSeason (`season_rankings_regular_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, RANK_MIN, RANK_FGM, RANK_FGA, RANK_FG_PCT, RANK_FG3M, RANK_FG3A, RANK_FG3_PCT, RANK_FTM, RANK_FTA, RANK_FT_PCT, RANK_OREB, RANK_DREB, RANK_REB, RANK_AST, RANK_STL, RANK_BLK, RANK_TOV, RANK_PTS, RANK_EFF
- SeasonTotalsAllStarSeason (`season_totals_all_star_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsCollegeSeason (`season_totals_college_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, ORGANIZATION_ID, SCHOOL_NAME, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsPostSeason (`season_totals_post_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsRegularSeason (`season_totals_regular_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS

## PlayerCompare

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playercompare.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playercompare?Conference=&DateFrom=&DateTo=&Division=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerIDList=202681%2C203078%2C2544%2C201567%2C203954&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=&VsPlayerIDList=201566%2C201939%2C201935%2C201142%2C203076`

```python
from nba_api.stats.endpoints import playercompare
endpoint = playercompare.PlayerCompare(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id_list='202681,203078,2544,201567,203954',
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_player_id_list='201566,201939,201935,201142,203076',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Individual (`individual`): GROUP_SET, DESCRIPTION, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS
- OverallCompare (`overall_compare`): GROUP_SET, DESCRIPTION, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS

## PlayerDashPtPass

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashptpass.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashptpass?DateFrom=&DateTo=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&PlayerID=2544&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashptpass
endpoint = playerdashptpass.PlayerDashPtPass(
    date_from_nullable="",
    date_to_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    player_id=2544,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PassesMade (`passes_made`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, TEAM_NAME, TEAM_ID, TEAM_ABBREVIATION, PASS_TYPE, G, PASS_TO, PASS_TEAMMATE_PLAYER_ID, FREQUENCY, PASS, AST, FGM, FGA, FG_PCT, FG2M, FG2A, FG2_PCT, FG3M, FG3A, FG3_PCT
- PassesReceived (`passes_received`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, TEAM_NAME, TEAM_ID, TEAM_ABBREVIATION, PASS_TYPE, G, PASS_FROM, PASS_TEAMMATE_PLAYER_ID, FREQUENCY, PASS, AST, FGM, FGA, FG_PCT, FG2M, FG2A, FG2_PCT, FG3M, FG3A, FG3_PCT

## PlayerDashPtReb

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashptreb.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashptreb?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&Period=0&PlayerID=2544&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashptreb
endpoint = playerdashptreb.PlayerDashPtReb(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    period=0,
    player_id=2544,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- NumContestedRebounding (`num_contested_rebounding`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, G, REB_NUM_CONTESTING_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- OverallRebounding (`overall_rebounding`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, G, OVERALL, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- RebDistanceRebounding (`reb_distance_rebounding`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, G, REB_DIST_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- ShotDistanceRebounding (`shot_distance_rebounding`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, G, SHOT_DIST_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- ShotTypeRebounding (`shot_type_rebounding`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, G, SHOT_TYPE_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT

## PlayerDashPtShotDefend

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashptshotdefend.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashptshotdefend?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&Period=0&PlayerID=2544&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashptshotdefend
endpoint = playerdashptshotdefend.PlayerDashPtShotDefend(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    period=0,
    player_id=2544,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DefendingShots (`defending_shots`): CLOSE_DEF_PERSON_ID, GP, G, DEFENSE_CATEGORY, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, PCT_PLUSMINUS

## PlayerDashPtShots

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashptshots.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashptshots?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&Period=0&PlayerID=2544&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashptshots
endpoint = playerdashptshots.PlayerDashPtShots(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    period=0,
    player_id=2544,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ClosestDefender10ftPlusShooting (`closest_defender10ft_plus_shooting`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, CLOSE_DEF_DIST_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- ClosestDefenderShooting (`closest_defender_shooting`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, CLOSE_DEF_DIST_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- DribbleShooting (`dribble_shooting`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, DRIBBLE_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- GeneralShooting (`general_shooting`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, SHOT_TYPE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- Overall (`overall`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, SHOT_TYPE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- ShotClockShooting (`shot_clock_shooting`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, SHOT_CLOCK_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- TouchTimeShooting (`touch_time_shooting`): PLAYER_ID, PLAYER_NAME_LAST_FIRST, SORT_ORDER, GP, G, TOUCH_TIME_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT

## PlayerDashboardByClutch

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbyclutch.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbyclutch?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbyclutch
endpoint = playerdashboardbyclutch.PlayerDashboardByClutch(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Last10Sec3Point2PlayerDashboard (`last10_sec3_point2_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last10Sec3PointPlayerDashboard (`last10_sec3_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last1Min5PointPlayerDashboard (`last1_min5_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last1MinPlusMinus5PointPlayerDashboard (`last1_min_plus_minus5_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last30Sec3Point2PlayerDashboard (`last30_sec3_point2_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last30Sec3PointPlayerDashboard (`last30_sec3_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last3Min5PointPlayerDashboard (`last3_min5_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last3MinPlusMinus5PointPlayerDashboard (`last3_min_plus_minus5_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last5Min5PointPlayerDashboard (`last5_min5_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last5MinPlusMinus5PointPlayerDashboard (`last5_min_plus_minus5_point_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## PlayerDashboardByGameSplits

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbygamesplits.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbygamesplits?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbygamesplits
endpoint = playerdashboardbygamesplits.PlayerDashboardByGameSplits(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ByActualMarginPlayerDashboard (`by_actual_margin_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- ByHalfPlayerDashboard (`by_half_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- ByPeriodPlayerDashboard (`by_period_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- ByScoreMarginPlayerDashboard (`by_score_margin_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## PlayerDashboardByGeneralSplits

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbygeneralsplits.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbygeneralsplits?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbygeneralsplits
endpoint = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DaysRestPlayerDashboard (`days_rest_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- LocationPlayerDashboard (`location_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- MonthPlayerDashboard (`month_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- PrePostAllStarPlayerDashboard (`pre_post_all_star_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- StartingPosition (`starting_position`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- WinsLossesPlayerDashboard (`wins_losses_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## PlayerDashboardByLastNGames

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbylastngames.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbylastngames?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbylastngames
endpoint = playerdashboardbylastngames.PlayerDashboardByLastNGames(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- GameNumberPlayerDashboard (`game_number_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last10PlayerDashboard (`last10_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last15PlayerDashboard (`last15_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last20PlayerDashboard (`last20_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- Last5PlayerDashboard (`last5_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## PlayerDashboardByShootingSplits

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbyshootingsplits.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbyshootingsplits?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbyshootingsplits
endpoint = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AssistedBy (`assisted_by`): GROUP_SET, PLAYER_ID, PLAYER_NAME, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- AssitedShotPlayerDashboard (`assited_shot_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- Shot5FTPlayerDashboard (`shot5_ft_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- Shot8FTPlayerDashboard (`shot8_ft_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- ShotAreaPlayerDashboard (`shot_area_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- ShotTypePlayerDashboard (`shot_type_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- ShotTypeSummaryPlayerDashboard (`shot_type_summary_player_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, CFID, CFPARAMS

## PlayerDashboardByTeamPerformance

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbyteamperformance.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbyteamperformance?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbyteamperformance
endpoint = playerdashboardbyteamperformance.PlayerDashboardByTeamPerformance(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- PointsScoredPlayerDashboard (`points_scored_player_dashboard`): GROUP_SET, GROUP_VALUE_ORDER, GROUP_VALUE, GROUP_VALUE_2, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- PontsAgainstPlayerDashboard (`ponts_against_player_dashboard`): GROUP_SET, GROUP_VALUE_ORDER, GROUP_VALUE, GROUP_VALUE_2, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- ScoreDifferentialPlayerDashboard (`score_differential_player_dashboard`): GROUP_SET, GROUP_VALUE_ORDER, GROUP_VALUE, GROUP_VALUE_2, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## PlayerDashboardByYearOverYear

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerdashboardbyyearoveryear.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerdashboardbyyearoveryear?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playerdashboardbyyearoveryear
endpoint = playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ByYearPlayerDashboard (`by_year_player_dashboard`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, MAX_GAME_DATE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS
- OverallPlayerDashboard (`overall_player_dashboard`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, MAX_GAME_DATE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## PlayerEstimatedMetrics

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerestimatedmetrics.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerestimatedmetrics?LeagueID=00&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import playerestimatedmetrics
endpoint = playerestimatedmetrics.PlayerEstimatedMetrics(
    league_id='00',
    season='2019-20',
    season_type='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerEstimatedMetrics (`player_estimated_metrics`): PLAYER_ID, PLAYER_NAME, GP, W, L, W_PCT, MIN, E_OFF_RATING, E_DEF_RATING, E_NET_RATING, E_AST_RATIO, E_OREB_PCT, E_DREB_PCT, E_REB_PCT, E_TOV_PCT, E_USG_PCT, E_PACE, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, E_OFF_RATING_RANK, E_DEF_RATING_RANK, E_NET_RATING_RANK, E_AST_RATIO_RANK, E_OREB_PCT_RANK, E_DREB_PCT_RANK, E_REB_PCT_RANK, E_TOV_PCT_RANK, E_USG_PCT_RANK, E_PACE_RANK

## PlayerFantasyProfileBarGraph

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerfantasyprofilebargraph.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerfantasyprofilebargraph?LeagueID=&PlayerID=2544&Season=2019-20&SeasonType=`

```python
from nba_api.stats.endpoints import playerfantasyprofilebargraph
endpoint = playerfantasyprofilebargraph.PlayerFantasyProfileBarGraph(
    league_id_nullable="",
    player_id=2544,
    season='2019-20',
    season_type_all_star_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LastFiveGamesAvg (`last_five_games_avg`): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, FAN_DUEL_PTS, NBA_FANTASY_PTS, PTS, REB, AST, FG3M, FT_PCT, STL, BLK, TOV, FG_PCT
- SeasonAvg (`season_avg`): PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, FAN_DUEL_PTS, NBA_FANTASY_PTS, PTS, REB, AST, FG3M, FT_PCT, STL, BLK, TOV, FG_PCT

## PlayerGameLog

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playergamelog.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playergamelog?DateFrom=&DateTo=&LeagueID=&PlayerID=2544&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import playergamelog
endpoint = playergamelog.PlayerGameLog(
    date_from_nullable="",
    date_to_nullable="",
    league_id_nullable="",
    player_id=2544,
    season='2019-20',
    season_type_all_star='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerGameLog (`player_game_log`): SEASON_ID, Player_ID, Game_ID, GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS, PLUS_MINUS, VIDEO_AVAILABLE

## PlayerGameLogs

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playergamelogs.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playergamelogs?DateFrom=&DateTo=&GameSegment=&LastNGames=&LeagueID=&Location=&MeasureType=&Month=&OpposingTeamID=&Outcome=&PORound=&PerMode=&Period=&PlayerID=&Season=&SeasonSegment=&SeasonType=&ShotClockRange=&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import playergamelogs
endpoint = playergamelogs.PlayerGameLogs(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games_nullable="",
    league_id_nullable="",
    location_nullable="",
    measure_type_player_game_logs_nullable="",
    month_nullable="",
    opp_team_id_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    per_mode_simple_nullable="",
    period_nullable="",
    player_id_nullable="",
    season_nullable="",
    season_segment_nullable="",
    season_type_nullable="",
    shot_clock_range_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerGameLogs (`player_game_logs`): SEASON_YEAR, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GAME_ID, GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK

## PlayerGameStreakFinder

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playergamestreakfinder.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playergamestreakfinder?ActiveStreaksOnly=&Conference=&DateFrom=&DateTo=&Division=&DraftNumber=&DraftRound=&DraftTeamID=&DraftYear=&EqAST=&EqBLK=&EqDD=&EqDREB=&EqFG3A=&EqFG3M=&EqFG3_PCT=&EqFGA=&EqFGM=&EqFG_PCT=&EqFTA=&EqFTM=&EqFT_PCT=&EqMINUTES=&EqOREB=&EqPF=&EqPTS=&EqREB=&EqSTL=&EqTD=&EqTOV=&GameID=&GtAST=&GtBLK=&GtDD=&GtDREB=&GtFG3A=&GtFG3M=&GtFG3_PCT=&GtFGA=&GtFGM=&GtFG_PCT=&GtFTA=&GtFTM=&GtFT_PCT=&GtMINUTES=&GtOREB=&GtPF=&GtPTS=&GtREB=&GtSTL=&GtTD=&GtTOV=&LeagueID=&Location=&LtAST=&LtBLK=&LtDD=&LtDREB=&LtFG3A=&LtFG3M=&LtFG3_PCT=&LtFGA=&LtFGM=&LtFG_PCT=&LtFTA=&LtFTM=&LtFT_PCT=&LtMINUTES=&LtOREB=&LtPF=&LtPTS=&LtREB=&LtSTL=&LtTD=&LtTOV=&MinGames=&Outcome=&PORound=&PlayerID=&RookieYear=&Season=&SeasonSegment=&SeasonType=&StarterBench=&TeamID=&VsConference=&VsDivision=&VsTeamID=&YearsExperience=`

```python
from nba_api.stats.endpoints import playergamestreakfinder
endpoint = playergamestreakfinder.PlayerGameStreakFinder(
    active_streaks_only_nullable="",
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    draft_number_nullable="",
    draft_round_nullable="",
    draft_team_id_nullable="",
    draft_year_nullable="",
    eq_ast_nullable="",
    eq_blk_nullable="",
    eq_dd_nullable="",
    eq_dreb_nullable="",
    eq_fg3a_nullable="",
    eq_fg3m_nullable="",
    eq_fga_nullable="",
    eq_fgm_nullable="",
    eq_fta_nullable="",
    eq_ftm_nullable="",
    eq_minutes_nullable="",
    eq_oreb_nullable="",
    eq_pf_nullable="",
    eq_pts_nullable="",
    eq_reb_nullable="",
    eq_stl_nullable="",
    eq_td_nullable="",
    eq_tov_nullable="",
    game_id_nullable="",
    gt_ast_nullable="",
    gt_blk_nullable="",
    gt_dd_nullable="",
    gt_dreb_nullable="",
    gt_fg3a_nullable="",
    gt_fg3m_nullable="",
    gt_fga_nullable="",
    gt_fgm_nullable="",
    gt_fta_nullable="",
    gt_ftm_nullable="",
    gt_minutes_nullable="",
    gt_oreb_nullable="",
    gt_pf_nullable="",
    gt_pts_nullable="",
    gt_reb_nullable="",
    gt_stl_nullable="",
    gt_td_nullable="",
    gt_tov_nullable="",
    league_id_nullable="",
    location_nullable="",
    lt_ast_nullable="",
    lt_blk_nullable="",
    lt_dd_nullable="",
    lt_dreb_nullable="",
    lt_fg3a_nullable="",
    lt_fg3m_nullable="",
    lt_fga_nullable="",
    lt_fgm_nullable="",
    lt_fta_nullable="",
    lt_ftm_nullable="",
    lt_minutes_nullable="",
    lt_oreb_nullable="",
    lt_pf_nullable="",
    lt_pts_nullable="",
    lt_reb_nullable="",
    lt_stl_nullable="",
    lt_td_nullable="",
    lt_tov_nullable="",
    min_games_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    player_id_nullable="",
    rookie_year_nullable="",
    season_nullable="",
    season_segment_nullable="",
    season_type_nullable="",
    starter_bench_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_team_id_nullable="",
    years_experience_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayerGameStreakFinderResults (`player_game_streak_finder_results`): PLAYER_NAME_LAST_FIRST, PLAYER_ID, GAMESTREAK, STARTDATE, ENDDATE, ACTIVESTREAK, NUMSEASONS, LASTSEASON, FIRSTSEASON

## PlayerNextNGames

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playernextngames.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playernextngames?LeagueID=&NumberOfGames=2147483647&PlayerID=2544&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import playernextngames
endpoint = playernextngames.PlayerNextNGames(
    league_id_nullable="",
    number_of_games=2147483647,
    player_id=2544,
    season_all='2019-20',
    season_type_all_star='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- NextNGames (`next_n_games`): GAME_ID, GAME_DATE, HOME_TEAM_ID, VISITOR_TEAM_ID, HOME_TEAM_NAME, VISITOR_TEAM_NAME, HOME_TEAM_ABBREVIATION, VISITOR_TEAM_ABBREVIATION, HOME_TEAM_NICKNAME, VISITOR_TEAM_NICKNAME, GAME_TIME, HOME_WL, VISITOR_WL

## PlayerProfileV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playerprofilev2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playerprofilev2?LeagueID=&PerMode=Totals&PlayerID=2544`

```python
from nba_api.stats.endpoints import playerprofilev2
endpoint = playerprofilev2.PlayerProfileV2(
    league_id_nullable="",
    per_mode36='Totals',
    player_id=2544,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- CareerHighs (`career_highs`): PLAYER_ID, GAME_DATE, VS_TEAM_ID, VS_TEAM_CITY, VS_TEAM_NAME, VS_TEAM_ABBREVIATION, STAT, STATS_VALUE, STAT_ORDER, DATE_EST
- CareerTotalsAllStarSeason (`career_totals_all_star_season`): PLAYER_ID, LEAGUE_ID, TEAM_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsCollegeSeason (`career_totals_college_season`): PLAYER_ID, LEAGUE_ID, ORGANIZATION_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsPostSeason (`career_totals_post_season`): PLAYER_ID, LEAGUE_ID, TEAM_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsPreseason (`career_totals_preseason`): PLAYER_ID, LEAGUE_ID, TEAM_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- CareerTotalsRegularSeason (`career_totals_regular_season`): PLAYER_ID, LEAGUE_ID, TEAM_ID, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- NextGame (`next_game`): GAME_ID, GAME_DATE, GAME_TIME, LOCATION, PLAYER_TEAM_ID, PLAYER_TEAM_CITY, PLAYER_TEAM_NICKNAME, PLAYER_TEAM_ABBREVIATION, VS_TEAM_ID, VS_TEAM_CITY, VS_TEAM_NICKNAME, VS_TEAM_ABBREVIATION
- SeasonHighs (`season_highs`): PLAYER_ID, GAME_DATE, VS_TEAM_ID, VS_TEAM_CITY, VS_TEAM_NAME, VS_TEAM_ABBREVIATION, STAT, STATS_VALUE, STAT_ORDER, DATE_EST
- SeasonRankingsPostSeason (`season_rankings_post_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, RANK_MIN, RANK_FGM, RANK_FGA, RANK_FG_PCT, RANK_FG3M, RANK_FG3A, RANK_FG3_PCT, RANK_FTM, RANK_FTA, RANK_FT_PCT, RANK_OREB, RANK_DREB, RANK_REB, RANK_AST, RANK_STL, RANK_BLK, RANK_TOV, RANK_PTS, RANK_EFF
- SeasonRankingsRegularSeason (`season_rankings_regular_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, RANK_MIN, RANK_FGM, RANK_FGA, RANK_FG_PCT, RANK_FG3M, RANK_FG3A, RANK_FG3_PCT, RANK_FTM, RANK_FTA, RANK_FT_PCT, RANK_OREB, RANK_DREB, RANK_REB, RANK_AST, RANK_STL, RANK_BLK, RANK_TOV, RANK_PTS, RANK_EFF
- SeasonTotalsAllStarSeason (`season_totals_all_star_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsCollegeSeason (`season_totals_college_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, ORGANIZATION_ID, SCHOOL_NAME, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsPostSeason (`season_totals_post_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsPreseason (`season_totals_preseason`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS
- SeasonTotalsRegularSeason (`season_totals_regular_season`): PLAYER_ID, SEASON_ID, LEAGUE_ID, TEAM_ID, TEAM_ABBREVIATION, PLAYER_AGE, GP, GS, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS

## PlayerVsPlayer

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playervsplayer.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playervsplayer?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=2544&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&VsConference=&VsDivision=&VsPlayerID=2544`

```python
from nba_api.stats.endpoints import playervsplayer
endpoint = playervsplayer.PlayerVsPlayer(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id=2544,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_player_id=2544,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- OnOffCourt (`on_off_court`): GROUP_SET, PLAYER_ID, PLAYER_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, CFID, CFPARAMS
- Overall (`overall`): GROUP_SET, GROUP_VALUE, PLAYER_ID, PLAYER_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, CFID, CFPARAMS
- PlayerInfo (`player_info`): PERSON_ID, FIRST_NAME, LAST_NAME, DISPLAY_FIRST_LAST, DISPLAY_LAST_COMMA_FIRST, DISPLAY_FI_LAST, BIRTHDATE, SCHOOL, COUNTRY, LAST_AFFILIATION
- ShotAreaOffCourt (`shot_area_off_court`): GROUP_SET, PLAYER_ID, PLAYER_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotAreaOnCourt (`shot_area_on_court`): GROUP_SET, PLAYER_ID, PLAYER_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotAreaOverall (`shot_area_overall`): GROUP_SET, GROUP_VALUE, PLAYER_ID, PLAYER_NAME, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotDistanceOffCourt (`shot_distance_off_court`): GROUP_SET, PLAYER_ID, PLAYER_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotDistanceOnCourt (`shot_distance_on_court`): GROUP_SET, PLAYER_ID, PLAYER_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotDistanceOverall (`shot_distance_overall`): GROUP_SET, GROUP_VALUE, PLAYER_ID, PLAYER_NAME, FGM, FGA, FG_PCT, CFID, CFPARAMS
- VsPlayerInfo (`vs_player_info`): PERSON_ID, FIRST_NAME, LAST_NAME, DISPLAY_FIRST_LAST, DISPLAY_LAST_COMMA_FIRST, DISPLAY_FI_LAST, BIRTHDATE, SCHOOL, COUNTRY, LAST_AFFILIATION

## PlayoffPicture

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/playoffpicture.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/playoffpicture?LeagueID=00&SeasonID=22019`

```python
from nba_api.stats.endpoints import playoffpicture
endpoint = playoffpicture.PlayoffPicture(
    league_id='00',
    season_id=22019,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- EastConfPlayoffPicture (`east_conf_playoff_picture`): CONFERENCE, HIGH_SEED_RANK, HIGH_SEED_TEAM, HIGH_SEED_TEAM_ID, LOW_SEED_RANK, LOW_SEED_TEAM, LOW_SEED_TEAM_ID, HIGH_SEED_SERIES_W, HIGH_SEED_SERIES_L, HIGH_SEED_SERIES_REMAINING_G, HIGH_SEED_SERIES_REMAINING_HOME_G, HIGH_SEED_SERIES_REMAINING_AWAY_G
- EastConfRemainingGames (`east_conf_remaining_games`): TEAM, TEAM_ID, REMAINING_G, REMAINING_HOME_G, REMAINING_AWAY_G
- EastConfStandings (`east_conf_standings`): CONFERENCE, RANK, TEAM, TEAM_SLUG, TEAM_ID, WINS, LOSSES, PCT, DIV, CONF, HOME, AWAY, GB, GR_OVER_500, GR_OVER_500_HOME, GR_OVER_500_AWAY, GR_UNDER_500, GR_UNDER_500_HOME, GR_UNDER_500_AWAY, RANKING_CRITERIA, CLINCHED_PLAYOFFS, CLINCHED_CONFERENCE, CLINCHED_DIVISION, Clinched_Play_In, ELIMINATED_PLAYOFFS, SOSA_REMAINING, ReturnToPlay_East_PI_Flag, ReturnToPlay_Already_Eliminated, Seeding_Game_1_Outcome, Seeding_Game_2_Outcome, Seeding_Game_3_Outcome, Seeding_Game_4_Outcome, Seeding_Game_5_Outcome, Seeding_Game_6_Outcome, Seeding_Game_7_Outcome, Seeding_Game_8_Outcome, Seeding_Game_1_ID, Seeding_Game_2_ID, Seeding_Game_3_ID, Seeding_Game_4_ID, Seeding_Game_5_ID, Seeding_Game_6_ID, Seeding_Game_7_ID, Seeding_Game_8_ID, Seeding_Game_1_Opponent, Seeding_Game_2_Opponent, Seeding_Game_3_Opponent, Seeding_Game_4_Opponent, Seeding_Game_5_Opponent, Seeding_Game_6_Opponent, Seeding_Game_7_Opponent, Seeding_Game_8_Opponent, Seeding_Game_1_Label, Seeding_Game_2_Label, Seeding_Game_3_Label, Seeding_Game_4_Label, Seeding_Game_5_Label, Seeding_Game_6_Label, Seeding_Game_7_Label, Seeding_Game_8_Label
- WestConfPlayoffPicture (`west_conf_playoff_picture`): CONFERENCE, HIGH_SEED_RANK, HIGH_SEED_TEAM, HIGH_SEED_TEAM_ID, LOW_SEED_RANK, LOW_SEED_TEAM, LOW_SEED_TEAM_ID, HIGH_SEED_SERIES_W, HIGH_SEED_SERIES_L, HIGH_SEED_SERIES_REMAINING_G, HIGH_SEED_SERIES_REMAINING_HOME_G, HIGH_SEED_SERIES_REMAINING_AWAY_G
- WestConfRemainingGames (`west_conf_remaining_games`): TEAM, TEAM_ID, REMAINING_G, REMAINING_HOME_G, REMAINING_AWAY_G
- WestConfStandings (`west_conf_standings`): CONFERENCE, RANK, TEAM, TEAM_SLUG, TEAM_ID, WINS, LOSSES, PCT, DIV, CONF, HOME, AWAY, GB, GR_OVER_500, GR_OVER_500_HOME, GR_OVER_500_AWAY, GR_UNDER_500, GR_UNDER_500_HOME, GR_UNDER_500_AWAY, RANKING_CRITERIA, CLINCHED_PLAYOFFS, CLINCHED_CONFERENCE, CLINCHED_DIVISION, Clinched_Play_In, ELIMINATED_PLAYOFFS, SOSA_REMAINING, ReturnToPlay_West_PI_Flag, ReturnToPlay_Already_Eliminated, Seeding_Game_1_Outcome, Seeding_Game_2_Outcome, Seeding_Game_3_Outcome, Seeding_Game_4_Outcome, Seeding_Game_5_Outcome, Seeding_Game_6_Outcome, Seeding_Game_7_Outcome, Seeding_Game_8_Outcome, Seeding_Game_1_ID, Seeding_Game_2_ID, Seeding_Game_3_ID, Seeding_Game_4_ID, Seeding_Game_5_ID, Seeding_Game_6_ID, Seeding_Game_7_ID, Seeding_Game_8_ID, Seeding_Game_1_Opponent, Seeding_Game_2_Opponent, Seeding_Game_3_Opponent, Seeding_Game_4_Opponent, Seeding_Game_5_Opponent, Seeding_Game_6_Opponent, Seeding_Game_7_Opponent, Seeding_Game_8_Opponent, Seeding_Game_1_Label, Seeding_Game_2_Label, Seeding_Game_3_Label, Seeding_Game_4_Label, Seeding_Game_5_Label, Seeding_Game_6_Label, Seeding_Game_7_Label, Seeding_Game_8_Label

## ScoreboardV2

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/scoreboardv2.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/scoreboardv2?DayOffset=0&GameDate=2020-08-16&LeagueID=00`

```python
from nba_api.stats.endpoints import scoreboardv2
endpoint = scoreboardv2.ScoreboardV2(
    day_offset=0,
    game_date='2020-08-16',
    league_id='00',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Available (`available`): GAME_ID, PT_AVAILABLE
- EastConfStandingsByDay (`east_conf_standings_by_day`): TEAM_ID, LEAGUE_ID, SEASON_ID, STANDINGSDATE, CONFERENCE, TEAM, G, W, L, W_PCT, HOME_RECORD, ROAD_RECORD, RETURNTOPLAY
- GameHeader (`game_header`): GAME_DATE_EST, GAME_SEQUENCE, GAME_ID, GAME_STATUS_ID, GAME_STATUS_TEXT, GAMECODE, HOME_TEAM_ID, VISITOR_TEAM_ID, SEASON, LIVE_PERIOD, LIVE_PC_TIME, NATL_TV_BROADCASTER_ABBREVIATION, HOME_TV_BROADCASTER_ABBREVIATION, AWAY_TV_BROADCASTER_ABBREVIATION, LIVE_PERIOD_TIME_BCAST, ARENA_NAME, WH_STATUS
- LastMeeting (`last_meeting`): GAME_ID, LAST_GAME_ID, LAST_GAME_DATE_EST, LAST_GAME_HOME_TEAM_ID, LAST_GAME_HOME_TEAM_CITY, LAST_GAME_HOME_TEAM_NAME, LAST_GAME_HOME_TEAM_ABBREVIATION, LAST_GAME_HOME_TEAM_POINTS, LAST_GAME_VISITOR_TEAM_ID, LAST_GAME_VISITOR_TEAM_CITY, LAST_GAME_VISITOR_TEAM_NAME, LAST_GAME_VISITOR_TEAM_CITY1, LAST_GAME_VISITOR_TEAM_POINTS
- LineScore (`line_score`): GAME_DATE_EST, GAME_SEQUENCE, GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY_NAME, TEAM_NAME, TEAM_WINS_LOSSES, PTS_QTR1, PTS_QTR2, PTS_QTR3, PTS_QTR4, PTS_OT1, PTS_OT2, PTS_OT3, PTS_OT4, PTS_OT5, PTS_OT6, PTS_OT7, PTS_OT8, PTS_OT9, PTS_OT10, PTS, FG_PCT, FT_PCT, FG3_PCT, AST, REB, TOV
- SeriesStandings (`series_standings`): GAME_ID, HOME_TEAM_ID, VISITOR_TEAM_ID, GAME_DATE_EST, HOME_TEAM_WINS, HOME_TEAM_LOSSES, SERIES_LEADER
- TeamLeaders (`team_leaders`): GAME_ID, TEAM_ID, TEAM_CITY, TEAM_NICKNAME, TEAM_ABBREVIATION, PTS_PLAYER_ID, PTS_PLAYER_NAME, PTS, REB_PLAYER_ID, REB_PLAYER_NAME, REB, AST_PLAYER_ID, AST_PLAYER_NAME, AST
- TicketLinks (`ticket_links`): GAME_ID, LEAG_TIX
- WestConfStandingsByDay (`west_conf_standings_by_day`): TEAM_ID, LEAGUE_ID, SEASON_ID, STANDINGSDATE, CONFERENCE, TEAM, G, W, L, W_PCT, HOME_RECORD, ROAD_RECORD
- WinProbability (`win_probability`): (empty)

## ShotChartDetail

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/shotchartdetail.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/shotchartdetail?AheadBehind=&ClutchTime=&ContextFilter=&ContextMeasure=PTS&DateFrom=&DateTo=&EndPeriod=&EndRange=&GameID=&GameSegment=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&Period=0&PlayerID=2544&PlayerPosition=&PointDiff=&Position=&RangeType=&RookieYear=&Season=&SeasonSegment=&SeasonType=Regular+Season&StartPeriod=&StartRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import shotchartdetail
endpoint = shotchartdetail.ShotChartDetail(
    ahead_behind_nullable="",
    clutch_time_nullable="",
    context_filter_nullable="",
    context_measure_simple='PTS',
    date_from_nullable="",
    date_to_nullable="",
    end_period_nullable="",
    end_range_nullable="",
    game_id_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    period=0,
    player_id=2544,
    player_position_nullable="",
    point_diff_nullable="",
    position_nullable="",
    range_type_nullable="",
    rookie_year_nullable="",
    season_nullable="",
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    start_period_nullable="",
    start_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- LeagueAverages (`league_averages`): GRID_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, FGA, FGM, FG_PCT
- Shot_Chart_Detail (`shot_chart_detail`): GRID_TYPE, GAME_ID, GAME_EVENT_ID, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_NAME, PERIOD, MINUTES_REMAINING, SECONDS_REMAINING, EVENT_TYPE, ACTION_TYPE, SHOT_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, SHOT_DISTANCE, LOC_X, LOC_Y, SHOT_ATTEMPTED_FLAG, SHOT_MADE_FLAG, GAME_DATE, HTM, VTM

## ShotChartLeagueWide

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/shotchartleaguewide.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/shotchartleaguewide?LeagueID=00&Season=2019-20`

```python
from nba_api.stats.endpoints import shotchartleaguewide
endpoint = shotchartleaguewide.ShotChartLeagueWide(
    league_id='00',
    season='2019-20',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- League_Wide (`league_wide`): GRID_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, FGA, FGM, FG_PCT

## ShotChartLineupDetail

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/shotchartlineupdetail.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/shotchartlineupdetail?ContextFilter=&ContextMeasure=PTS&DateFrom=&DateTo=&GROUP_ID=0&GameID=&GameSegment=&LastNGames=&LeagueID=00&Location=&Month=&OpponentTeamID=&Outcome=&Period=0&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import shotchartlineupdetail
endpoint = shotchartlineupdetail.ShotChartLineupDetail(
    context_filter_nullable="",
    context_measure_detailed='PTS',
    date_from_nullable="",
    date_to_nullable="",
    game_id_nullable="",
    game_segment_nullable="",
    last_n_games_nullable="",
    league_id='00',
    location_nullable="",
    month_nullable="",
    opponent_team_id_nullable="",
    outcome_nullable="",
    period=0,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ShotChartLineupDetail (`shot_chart_lineup_detail`): GRID_TYPE, GAME_ID, GAME_EVENT_ID, GROUP_ID, GROUP_NAME, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_NAME, PERIOD, MINUTES_REMAINING, SECONDS_REMAINING, EVENT_TYPE, ACTION_TYPE, SHOT_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, SHOT_DISTANCE, LOC_X, LOC_Y, SHOT_ATTEMPTED_FLAG, SHOT_MADE_FLAG, GAME_DATE, HTM, VTM
- ShotChartLineupLeagueAverage (`shot_chart_lineup_league_average`): GRID_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, FGA, FGM, FG_PCT

## SynergyPlayTypes

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/synergyplaytypes.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/synergyplaytypes?LeagueID=00&PerMode=Totals&PlayType=&PlayerOrTeam=T&SeasonType=Regular+Season&SeasonYear=2019-20&TypeGrouping=`

```python
from nba_api.stats.endpoints import synergyplaytypes
endpoint = synergyplaytypes.SynergyPlayTypes(
    league_id='00',
    per_mode_simple='Totals',
    play_type_nullable="",
    player_or_team_abbreviation='T',
    season_type_all_star='Regular Season',
    season='2019-20',
    type_grouping_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- SynergyPlayType (`synergy_play_type`): SEASON_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, PLAY_TYPE, TYPE_GROUPING, PERCENTILE, GP, POSS_PCT, PPP, FG_PCT, FT_POSS_PCT, TOV_POSS_PCT, SF_POSS_PCT, PLUSONE_POSS_PCT, SCORE_POSS_PCT, EFG_PCT, POSS, PTS, FGM, FGA, FGMX

## TeamAndPlayersVsPlayers

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamandplayersvsplayers.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamandplayersvsplayers?Conference=&DateFrom=&DateTo=&Division=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID1=202681&PlayerID2=203078&PlayerID3=203507&PlayerID4=201567&PlayerID5=203954&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=1610612739&VsConference=&VsDivision=&VsPlayerID1=201566&VsPlayerID2=201939&VsPlayerID3=201935&VsPlayerID4=201142&VsPlayerID5=203076&VsTeamID=1610612765`

```python
from nba_api.stats.endpoints import teamandplayersvsplayers
endpoint = teamandplayersvsplayers.TeamAndPlayersVsPlayers(
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id1=202681,
    player_id2=203078,
    player_id3=203507,
    player_id4=201567,
    player_id5=203954,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    shot_clock_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_player_id1=201566,
    vs_player_id2=201939,
    vs_player_id3=201935,
    vs_player_id4=201142,
    vs_player_id5=203076,
    vs_team_id=1610612765,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayersVsPlayers (`players_vs_players`): GROUP_SET, TITLE_DESCRIPTION, DESCRIPTION, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS
- TeamPlayersVsPlayersOff (`team_players_vs_players_off`): GROUP_SET, TITLE_DESCRIPTION, PLAYER_ID, PLAYER_NAME, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS
- TeamPlayersVsPlayersOn (`team_players_vs_players_on`): GROUP_SET, TITLE_DESCRIPTION, PLAYER_ID, PLAYER_NAME, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS
- TeamVsPlayers (`team_vs_players`): GROUP_SET, TITLE_DESCRIPTION, DESCRIPTION, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS
- TeamVsPlayersOff (`team_vs_players_off`): GROUP_SET, TITLE_DESCRIPTION, DESCRIPTION, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS

## TeamDashLineups

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdashlineups.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdashlineups?DateFrom=&DateTo=&GameID=&GameSegment=&GroupQuantity=5&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamdashlineups
endpoint = teamdashlineups.TeamDashLineups(
    date_from_nullable="",
    date_to_nullable="",
    game_id_nullable="",
    game_segment_nullable="",
    group_quantity=5,
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- Lineups (`lineups`): GROUP_SET, GROUP_ID, GROUP_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK
- Overall (`overall`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK

## TeamDashPtPass

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdashptpass.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdashptpass?DateFrom=&DateTo=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamdashptpass
endpoint = teamdashptpass.TeamDashPtPass(
    date_from_nullable="",
    date_to_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PassesMade (`passes_made`): TEAM_ID, TEAM_NAME, PASS_TYPE, G, PASS_FROM, PASS_TEAMMATE_PLAYER_ID, FREQUENCY, PASS, AST, FGM, FGA, FG_PCT, FG2M, FG2A, FG2_PCT, FG3M, FG3A, FG3_PCT
- PassesReceived (`passes_received`): TEAM_ID, TEAM_NAME, PASS_TYPE, G, PASS_TO, PASS_TEAMMATE_PLAYER_ID, FREQUENCY, PASS, AST, FGM, FGA, FG_PCT, FG2M, FG2A, FG2_PCT, FG3M, FG3A, FG3_PCT

## TeamDashPtReb

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdashptreb.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdashptreb?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&Period=0&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamdashptreb
endpoint = teamdashptreb.TeamDashPtReb(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    period=0,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- NumContestedRebounding (`num_contested_rebounding`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, REB_NUM_CONTESTING_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- OverallRebounding (`overall_rebounding`): TEAM_ID, TEAM_NAME, G, OVERALL, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- RebDistanceRebounding (`reb_distance_rebounding`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, REB_DIST_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- ShotDistanceRebounding (`shot_distance_rebounding`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, SHOT_DIST_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT
- ShotTypeRebounding (`shot_type_rebounding`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, SHOT_TYPE_RANGE, REB_FREQUENCY, OREB, DREB, REB, C_OREB, C_DREB, C_REB, C_REB_PCT, UC_OREB, UC_DREB, UC_REB, UC_REB_PCT

## TeamDashPtShots

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdashptshots.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdashptshots?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=00&Location=&Month=0&OpponentTeamID=0&Outcome=&PerMode=Totals&Period=0&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamdashptshots
endpoint = teamdashptshots.TeamDashPtShots(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id='00',
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    per_mode_simple='Totals',
    period=0,
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- ClosestDefender10ftPlusShooting (`closest_defender10ft_plus_shooting`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, CLOSE_DEF_DIST_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- ClosestDefenderShooting (`closest_defender_shooting`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, CLOSE_DEF_DIST_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- DribbleShooting (`dribble_shooting`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, DRIBBLE_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- GeneralShooting (`general_shooting`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, SHOT_TYPE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- ShotClockShooting (`shot_clock_shooting`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, SHOT_CLOCK_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT
- TouchTimeShooting (`touch_time_shooting`): TEAM_ID, TEAM_NAME, SORT_ORDER, G, TOUCH_TIME_RANGE, FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2A_FREQUENCY, FG2M, FG2A, FG2_PCT, FG3A_FREQUENCY, FG3M, FG3A, FG3_PCT

## TeamDashboardByGeneralSplits

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdashboardbygeneralsplits.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdashboardbygeneralsplits?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamdashboardbygeneralsplits
endpoint = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- DaysRestTeamDashboard (`days_rest_team_dashboard`): GROUP_SET, GROUP_VALUE, TEAM_DAYS_REST_RANGE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- LocationTeamDashboard (`location_team_dashboard`): GROUP_SET, GROUP_VALUE, TEAM_GAME_LOCATION, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- MonthTeamDashboard (`month_team_dashboard`): GROUP_SET, GROUP_VALUE, SEASON_MONTH_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- OverallTeamDashboard (`overall_team_dashboard`): GROUP_SET, GROUP_VALUE, SEASON_YEAR, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- PrePostAllStarTeamDashboard (`pre_post_all_star_team_dashboard`): GROUP_SET, GROUP_VALUE, SEASON_SEGMENT, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- WinsLossesTeamDashboard (`wins_losses_team_dashboard`): GROUP_SET, GROUP_VALUE, GAME_RESULT, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS

## TeamDashboardByShootingSplits

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdashboardbyshootingsplits.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdashboardbyshootingsplits?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamdashboardbyshootingsplits
endpoint = teamdashboardbyshootingsplits.TeamDashboardByShootingSplits(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AssistedBy (`assisted_by`): GROUP_SET, PLAYER_ID, PLAYER_NAME, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- AssitedShotTeamDashboard (`assited_shot_team_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- OverallTeamDashboard (`overall_team_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- Shot5FTTeamDashboard (`shot5_ft_team_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- Shot8FTTeamDashboard (`shot8_ft_team_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- ShotAreaTeamDashboard (`shot_area_team_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS
- ShotTypeTeamDashboard (`shot_type_team_dashboard`): GROUP_SET, GROUP_VALUE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT, BLKA, PCT_AST_2PM, PCT_UAST_2PM, PCT_AST_3PM, PCT_UAST_3PM, PCT_AST_FGM, PCT_UAST_FGM, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, EFG_PCT_RANK, BLKA_RANK, PCT_AST_2PM_RANK, PCT_UAST_2PM_RANK, PCT_AST_3PM_RANK, PCT_UAST_3PM_RANK, PCT_AST_FGM_RANK, PCT_UAST_FGM_RANK, CFID, CFPARAMS

## TeamDetails

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamdetails.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamdetails?TeamID=1610612739`

```python
from nba_api.stats.endpoints import teamdetails
endpoint = teamdetails.TeamDetails(
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- TeamAwardsChampionships (`team_awards_championships`): YEARAWARDED, OPPOSITETEAM
- TeamAwardsConf (`team_awards_conf`): YEARAWARDED, OPPOSITETEAM
- TeamAwardsDiv (`team_awards_div`): YEARAWARDED, OPPOSITETEAM
- TeamBackground (`team_background`): TEAM_ID, ABBREVIATION, NICKNAME, YEARFOUNDED, CITY, ARENA, ARENACAPACITY, OWNER, GENERALMANAGER, HEADCOACH, DLEAGUEAFFILIATION
- TeamHistory (`team_history`): TEAM_ID, CITY, NICKNAME, YEARFOUNDED, YEARACTIVETILL
- TeamHof (`team_hof`): PLAYERID, PLAYER, POSITION, JERSEY, SEASONSWITHTEAM, YEAR
- TeamRetired (`team_retired`): PLAYERID, PLAYER, POSITION, JERSEY, SEASONSWITHTEAM, YEAR
- TeamSocialSites (`team_social_sites`): ACCOUNTTYPE, WEBSITE_LINK

## TeamEstimatedMetrics

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamestimatedmetrics.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamestimatedmetrics?LeagueID=00&Season=2019-20&SeasonType=Regular+Season`

```python
from nba_api.stats.endpoints import teamestimatedmetrics
endpoint = teamestimatedmetrics.TeamEstimatedMetrics(
    league_id='00',
    season='2019-20',
    season_type='Regular Season',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- TeamEstimatedMetrics (`team_estimated_metrics`): TEAM_NAME, TEAM_ID, GP, W, L, W_PCT, MIN, E_OFF_RATING, E_DEF_RATING, E_NET_RATING, E_PACE, E_AST_RATIO, E_OREB_PCT, E_DREB_PCT, E_REB_PCT, E_TM_TOV_PCT, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, E_OFF_RATING_RANK, E_DEF_RATING_RANK, E_NET_RATING_RANK, E_AST_RATIO_RANK, E_OREB_PCT_RANK, E_DREB_PCT_RANK, E_REB_PCT_RANK, E_TM_TOV_PCT_RANK, E_PACE_RANK

## TeamGameStreakFinder

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamgamestreakfinder.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamgamestreakfinder?ActiveStreaksOnly=&ActiveTeamsOnly=&BtrOPPAST=&BtrOPPBLK=&BtrOPPDREB=&BtrOPPFG3A=&BtrOPPFG3M=&BtrOPPFG3PCT=&BtrOPPFGA=&BtrOPPFGM=&BtrOPPFG_PCT=&BtrOPPFTA=&BtrOPPFTM=&BtrOPPFT_PCT=&BtrOPPOREB=&BtrOPPPF=&BtrOPPPTS=&BtrOPPPTS2NDCHANCE=&BtrOPPPTSFB=&BtrOPPPTSOFFTOV=&BtrOPPPTSPAINT=&BtrOPPREB=&BtrOPPSTL=&BtrOPPTOV=&Conference=&DateFrom=&DateTo=&Division=&EqAST=&EqBLK=&EqDD=&EqDREB=&EqFG3A=&EqFG3M=&EqFG3_PCT=&EqFGA=&EqFGM=&EqFG_PCT=&EqFTA=&EqFTM=&EqFT_PCT=&EqMINUTES=&EqOPPPTS2NDCHANCE=&EqOPPPTSFB=&EqOPPPTSOFFTOV=&EqOPPPTSPAINT=&EqOREB=&EqPF=&EqPTS=&EqPTS2NDCHANCE=&EqPTSFB=&EqPTSOFFTOV=&EqPTSPAINT=&EqREB=&EqSTL=&EqTD=&EqTOV=&GameID=&GtAST=&GtBLK=&GtDD=&GtDREB=&GtFG3A=&GtFG3M=&GtFG3_PCT=&GtFGA=&GtFGM=&GtFG_PCT=&GtFTA=&GtFTM=&GtFT_PCT=&GtMINUTES=&GtOPPAST=&GtOPPBLK=&GtOPPDREB=&GtOPPFG3A=&GtOPPFG3M=&GtOPPFG3PCT=&GtOPPFGA=&GtOPPFGM=&GtOPPFG_PCT=&GtOPPFTA=&GtOPPFTM=&GtOPPFT_PCT=&GtOPPOREB=&GtOPPPF=&GtOPPPTS=&GtOPPPTS2NDCHANCE=&GtOPPPTSFB=&GtOPPPTSOFFTOV=&GtOPPPTSPAINT=&GtOPPREB=&GtOPPSTL=&GtOPPTOV=&GtOREB=&GtPF=&GtPTS=&GtPTS2NDCHANCE=&GtPTSFB=&GtPTSOFFTOV=&GtPTSPAINT=&GtREB=&GtSTL=&GtTD=&GtTOV=&LStreak=&LeagueID=&Location=&LtAST=&LtBLK=&LtDD=&LtDREB=&LtFG3A=&LtFG3M=&LtFG3_PCT=&LtFGA=&LtFGM=&LtFG_PCT=&LtFTA=&LtFTM=&LtFT_PCT=&LtMINUTES=&LtOPPAST=&LtOPPBLK=&LtOPPDREB=&LtOPPFG3A=&LtOPPFG3M=&LtOPPFG3PCT=&LtOPPFGA=&LtOPPFGM=&LtOPPFG_PCT=&LtOPPFTA=&LtOPPFTM=&LtOPPFT_PCT=&LtOPPOREB=&LtOPPPF=&LtOPPPTS=&LtOPPPTS2NDCHANCE=&LtOPPPTSFB=&LtOPPPTSOFFTOV=&LtOPPPTSPAINT=&LtOPPREB=&LtOPPSTL=&LtOPPTOV=&LtOREB=&LtPF=&LtPTS=&LtPTS2NDCHANCE=&LtPTSFB=&LtPTSOFFTOV=&LtPTSPAINT=&LtREB=&LtSTL=&LtTD=&LtTOV=&MinGames=&Outcome=&PORound=&Season=&SeasonSegment=&SeasonType=&TeamID=&VsConference=&VsDivision=&VsTeamID=&WStreak=&WrsOPPAST=&WrsOPPBLK=&WrsOPPDREB=&WrsOPPFG3A=&WrsOPPFG3M=&WrsOPPFG3PCT=&WrsOPPFGA=&WrsOPPFGM=&WrsOPPFG_PCT=&WrsOPPFTA=&WrsOPPFTM=&WrsOPPFT_PCT=&WrsOPPOREB=&WrsOPPPF=&WrsOPPPTS=&WrsOPPPTS2NDCHANCE=&WrsOPPPTSFB=&WrsOPPPTSOFFTOV=&WrsOPPPTSPAINT=&WrsOPPREB=&WrsOPPSTL=&WrsOPPTOV=`

```python
from nba_api.stats.endpoints import teamgamestreakfinder
endpoint = teamgamestreakfinder.TeamGameStreakFinder(
    active_streaks_only_nullable="",
    active_teams_only_nullable="",
    btr_opp_ast_nullable="",
    btr_opp_blk_nullable="",
    btr_opp_dreb_nullable="",
    btr_opp_fg3a_nullable="",
    btr_opp_fg3m_nullable="",
    btr_opp_fg3_pct_nullable="",
    btr_opp_fga_nullable="",
    btr_opp_fgm_nullable="",
    btr_opp_fta_nullable="",
    btr_opp_ftm_nullable="",
    btr_opp_oreb_nullable="",
    btr_opp_pf_nullable="",
    btr_opp_pts_nullable="",
    btr_opp_pts2nd_chance_nullable="",
    btr_opp_pts_fb_nullable="",
    btr_opp_pts_off_tov_nullable="",
    btr_opp_pts_paint_nullable="",
    btr_opp_reb_nullable="",
    btr_opp_stl_nullable="",
    btr_opp_tov_nullable="",
    conference_nullable="",
    date_from_nullable="",
    date_to_nullable="",
    division_simple_nullable="",
    eq_ast_nullable="",
    eq_blk_nullable="",
    eq_dd_nullable="",
    eq_dreb_nullable="",
    eq_fg3a_nullable="",
    eq_fg3m_nullable="",
    eq_fga_nullable="",
    eq_fgm_nullable="",
    eq_fta_nullable="",
    eq_ftm_nullable="",
    eq_minutes_nullable="",
    eq_opp_pts2nd_chance_nullable="",
    eq_opp_pts_fb_nullable="",
    eq_opp_pts_off_tov_nullable="",
    eq_opp_pts_paint_nullable="",
    eq_oreb_nullable="",
    eq_pf_nullable="",
    eq_pts_nullable="",
    eq_pts2nd_chance_nullable="",
    eq_pts_fb_nullable="",
    eq_pts_off_tov_nullable="",
    eq_pts_paint_nullable="",
    eq_reb_nullable="",
    eq_stl_nullable="",
    eq_td_nullable="",
    eq_tov_nullable="",
    game_id_nullable="",
    gt_ast_nullable="",
    gt_blk_nullable="",
    gt_dd_nullable="",
    gt_dreb_nullable="",
    gt_fg3a_nullable="",
    gt_fg3m_nullable="",
    gt_fga_nullable="",
    gt_fgm_nullable="",
    gt_fta_nullable="",
    gt_ftm_nullable="",
    gt_minutes_nullable="",
    gt_opp_ast_nullable="",
    gt_opp_blk_nullable="",
    gt_opp_dreb_nullable="",
    gt_opp_fg3a_nullable="",
    gt_opp_fg3m_nullable="",
    gt_opp_fg3_pct_nullable="",
    gt_opp_fga_nullable="",
    gt_opp_fgm_nullable="",
    gt_opp_fta_nullable="",
    gt_opp_ftm_nullable="",
    gt_opp_oreb_nullable="",
    gt_opp_pf_nullable="",
    gt_opp_pts_nullable="",
    gt_opp_pts2nd_chance_nullable="",
    gt_opp_pts_fb_nullable="",
    gt_opp_pts_off_tov_nullable="",
    gt_opp_pts_paint_nullable="",
    gt_opp_reb_nullable="",
    gt_opp_stl_nullable="",
    gt_opp_tov_nullable="",
    gt_oreb_nullable="",
    gt_pf_nullable="",
    gt_pts_nullable="",
    gt_pts2nd_chance_nullable="",
    gt_pts_fb_nullable="",
    gt_pts_off_tov_nullable="",
    gt_pts_paint_nullable="",
    gt_reb_nullable="",
    gt_stl_nullable="",
    gt_td_nullable="",
    gt_tov_nullable="",
    lstreak_nullable="",
    league_id_nullable="",
    location_nullable="",
    lt_ast_nullable="",
    lt_blk_nullable="",
    lt_dd_nullable="",
    lt_dreb_nullable="",
    lt_fg3a_nullable="",
    lt_fg3m_nullable="",
    lt_fga_nullable="",
    lt_fgm_nullable="",
    lt_fta_nullable="",
    lt_ftm_nullable="",
    lt_minutes_nullable="",
    lt_opp_ast_nullable="",
    lt_opp_blk_nullable="",
    lt_opp_dreb_nullable="",
    lt_opp_fg3a_nullable="",
    lt_opp_fg3m_nullable="",
    lt_opp_fg3_pct_nullable="",
    lt_opp_fga_nullable="",
    lt_opp_fgm_nullable="",
    lt_opp_fta_nullable="",
    lt_opp_ftm_nullable="",
    lt_opp_oreb_nullable="",
    lt_opp_pf_nullable="",
    lt_opp_pts_nullable="",
    lt_opp_pts2nd_chance_nullable="",
    lt_opp_pts_fb_nullable="",
    lt_opp_pts_off_tov_nullable="",
    lt_opp_pts_paint_nullable="",
    lt_opp_reb_nullable="",
    lt_opp_stl_nullable="",
    lt_opp_tov_nullable="",
    lt_oreb_nullable="",
    lt_pf_nullable="",
    lt_pts_nullable="",
    lt_pts2nd_chance_nullable="",
    lt_pts_fb_nullable="",
    lt_pts_off_tov_nullable="",
    lt_pts_paint_nullable="",
    lt_reb_nullable="",
    lt_stl_nullable="",
    lt_td_nullable="",
    lt_tov_nullable="",
    min_games_nullable="",
    outcome_nullable="",
    po_round_nullable="",
    season_nullable="",
    season_segment_nullable="",
    season_type_nullable="",
    team_id_nullable="",
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_team_id_nullable="",
    wstreak_nullable="",
    wrs_opp_ast_nullable="",
    wrs_opp_blk_nullable="",
    wrs_opp_dreb_nullable="",
    wrs_opp_fg3a_nullable="",
    wrs_opp_fg3m_nullable="",
    wrs_opp_fg3_pct_nullable="",
    wrs_opp_fga_nullable="",
    wrs_opp_fgm_nullable="",
    wrs_opp_fta_nullable="",
    wrs_opp_ftm_nullable="",
    wrs_opp_oreb_nullable="",
    wrs_opp_pf_nullable="",
    wrs_opp_pts_nullable="",
    wrs_opp_pts2nd_chance_nullable="",
    wrs_opp_pts_fb_nullable="",
    wrs_opp_pts_off_tov_nullable="",
    wrs_opp_pts_paint_nullable="",
    wrs_opp_reb_nullable="",
    wrs_opp_stl_nullable="",
    wrs_opp_tov_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- TeamGameStreakFinderParametersResults (`team_game_streak_finder_parameters_results`): TEAM_NAME, TEAM_ID, GAMESTREAK, STARTDATE, ENDDATE, ACTIVESTREAK, NUMSEASONS, LASTSEASON, FIRSTSEASON, ABBREVIATION

## TeamInfoCommon

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teaminfocommon.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teaminfocommon?LeagueID=00&Season=&SeasonType=&TeamID=1610612739`

```python
from nba_api.stats.endpoints import teaminfocommon
endpoint = teaminfocommon.TeamInfoCommon(
    league_id='00',
    season_nullable="",
    season_type_nullable="",
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- AvailableSeasons (`available_seasons`): SEASON_ID
- TeamInfoCommon (`team_info_common`): TEAM_ID, SEASON_YEAR, TEAM_CITY, TEAM_NAME, TEAM_ABBREVIATION, TEAM_CONFERENCE, TEAM_DIVISION, TEAM_CODE, W, L, PCT, CONF_RANK, DIV_RANK, MIN_YEAR, MAX_YEAR
- TeamSeasonRanks (`team_season_ranks`): LEAGUE_ID, SEASON_ID, TEAM_ID, PTS_RANK, PTS_PG, REB_RANK, REB_PG, AST_RANK, AST_PG, OPP_PTS_RANK, OPP_PTS_PG

## TeamPlayerDashboard

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamplayerdashboard.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamplayerdashboard?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PORound=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&ShotClockRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamplayerdashboard
endpoint = teamplayerdashboard.TeamPlayerDashboard(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    po_round_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    shot_clock_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- PlayersSeasonTotals (`players_season_totals`): GROUP_SET, PLAYER_ID, PLAYER_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK
- TeamOverall (`team_overall`): GROUP_SET, TEAM_ID, TEAM_NAME, GROUP_VALUE, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK

## TeamPlayerOnOffDetails

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamplayeronoffdetails.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamplayeronoffdetails?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamplayeronoffdetails
endpoint = teamplayeronoffdetails.TeamPlayerOnOffDetails(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- OverallTeamPlayerOnOffDetails (`overall_team_player_on_off_details`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK
- PlayersOffCourtTeamPlayerOnOffDetails (`players_off_court_team_player_on_off_details`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK
- PlayersOnCourtTeamPlayerOnOffDetails (`players_on_court_team_player_on_off_details`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK

## TeamPlayerOnOffSummary

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamplayeronoffsummary.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamplayeronoffsummary?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import teamplayeronoffsummary
endpoint = teamplayeronoffsummary.TeamPlayerOnOffSummary(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- OverallTeamPlayerOnOffSummary (`overall_team_player_on_off_summary`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK
- PlayersOffCourtTeamPlayerOnOffSummary (`players_off_court_team_player_on_off_summary`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, MIN, PLUS_MINUS, OFF_RATING, DEF_RATING, NET_RATING
- PlayersOnCourtTeamPlayerOnOffSummary (`players_on_court_team_player_on_off_summary`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, MIN, PLUS_MINUS, OFF_RATING, DEF_RATING, NET_RATING

## TeamVsPlayer

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamvsplayer.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamvsplayer?DateFrom=&DateTo=&GameSegment=&LastNGames=0&LeagueID=&Location=&MeasureType=Base&Month=0&OpponentTeamID=0&Outcome=&PaceAdjust=N&PerMode=Totals&Period=0&PlayerID=&PlusMinus=N&Rank=N&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&TeamID=1610612739&VsConference=&VsDivision=&VsPlayerID=2544`

```python
from nba_api.stats.endpoints import teamvsplayer
endpoint = teamvsplayer.TeamVsPlayer(
    date_from_nullable="",
    date_to_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    measure_type_detailed_defense='Base',
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    pace_adjust='N',
    per_mode_detailed='Totals',
    period=0,
    player_id_nullable="",
    plus_minus='N',
    rank='N',
    season='2019-20',
    season_segment_nullable="",
    season_type_playoffs='Regular Season',
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
    vs_player_id=2544,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- OnOffCourt (`on_off_court`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- Overall (`overall`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, CFID, CFPARAMS
- ShotAreaOffCourt (`shot_area_off_court`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotAreaOnCourt (`shot_area_on_court`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotAreaOverall (`shot_area_overall`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotDistanceOffCourt (`shot_distance_off_court`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotDistanceOnCourt (`shot_distance_on_court`): GROUP_SET, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS, GROUP_VALUE, FGM, FGA, FG_PCT, CFID, CFPARAMS
- ShotDistanceOverall (`shot_distance_overall`): GROUP_SET, GROUP_VALUE, TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME, FGM, FGA, FG_PCT, CFID, CFPARAMS
- vsPlayerOverall (`vs_player_overall`): GROUP_SET, GROUP_VALUE, PLAYER_ID, GP, W, L, W_PCT, MIN, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, TOV, STL, BLK, BLKA, PF, PFD, PTS, PLUS_MINUS, NBA_FANTASY_PTS, DD2, TD3, GP_RANK, W_RANK, L_RANK, W_PCT_RANK, MIN_RANK, FGM_RANK, FGA_RANK, FG_PCT_RANK, FG3M_RANK, FG3A_RANK, FG3_PCT_RANK, FTM_RANK, FTA_RANK, FT_PCT_RANK, OREB_RANK, DREB_RANK, REB_RANK, AST_RANK, TOV_RANK, STL_RANK, BLK_RANK, BLKA_RANK, PF_RANK, PFD_RANK, PTS_RANK, PLUS_MINUS_RANK, NBA_FANTASY_PTS_RANK, DD2_RANK, TD3_RANK, CFID, CFPARAMS

## TeamYearByYearStats

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/teamyearbyyearstats.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/teamyearbyyearstats?LeagueID=00&PerMode=Totals&SeasonType=Regular+Season&TeamID=1610612739`

```python
from nba_api.stats.endpoints import teamyearbyyearstats
endpoint = teamyearbyyearstats.TeamYearByYearStats(
    league_id='00',
    per_mode_simple='Totals',
    season_type_all_star='Regular Season',
    team_id=1610612739,
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- TeamStats (`team_stats`): TEAM_ID, TEAM_CITY, TEAM_NAME, YEAR, GP, WINS, LOSSES, WIN_PCT, CONF_RANK, DIV_RANK, PO_WINS, PO_LOSSES, CONF_COUNT, DIV_COUNT, NBA_FINALS_APPEARANCE, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, OREB, DREB, REB, AST, PF, STL, TOV, BLK, PTS, PTS_RANK

## VideoDetails

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/videodetails.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/videodetails?AheadBehind=&ClutchTime=&ContextFilter=&ContextMeasure=PTS&DateFrom=&DateTo=&EndPeriod=&EndRange=&GameID=&GameSegment=&LastNGames=0&LeagueID=&Location=&Month=0&OpponentTeamID=0&Outcome=&Period=0&PlayerID=2544&PointDiff=&Position=&RangeType=&RookieYear=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&StartPeriod=&StartRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import videodetails
endpoint = videodetails.VideoDetails(
    ahead_behind_nullable="",
    clutch_time_nullable="",
    context_filter_nullable="",
    context_measure_detailed='PTS',
    date_from_nullable="",
    date_to_nullable="",
    end_period_nullable="",
    end_range_nullable="",
    game_id_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    period=0,
    player_id=2544,
    point_diff_nullable="",
    position_nullable="",
    range_type_nullable="",
    rookie_year_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    start_period_nullable="",
    start_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

## VideoDetailsAsset

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/videodetailsasset.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/videodetailsasset?AheadBehind=&ClutchTime=&ContextFilter=&ContextMeasure=PTS&DateFrom=&DateTo=&EndPeriod=&EndRange=&GameID=&GameSegment=&LastNGames=0&LeagueID=&Location=&Month=0&OpponentTeamID=0&Outcome=&Period=0&PlayerID=2544&PointDiff=&Position=&RangeType=&RookieYear=&Season=2019-20&SeasonSegment=&SeasonType=Regular+Season&StartPeriod=&StartRange=&TeamID=1610612739&VsConference=&VsDivision=`

```python
from nba_api.stats.endpoints import videodetailsasset
endpoint = videodetailsasset.VideoDetailsAsset(
    ahead_behind_nullable="",
    clutch_time_nullable="",
    context_filter_nullable="",
    context_measure_detailed='PTS',
    date_from_nullable="",
    date_to_nullable="",
    end_period_nullable="",
    end_range_nullable="",
    game_id_nullable="",
    game_segment_nullable="",
    last_n_games=0,
    league_id_nullable="",
    location_nullable="",
    month=0,
    opponent_team_id=0,
    outcome_nullable="",
    period=0,
    player_id=2544,
    point_diff_nullable="",
    position_nullable="",
    range_type_nullable="",
    rookie_year_nullable="",
    season='2019-20',
    season_segment_nullable="",
    season_type_all_star='Regular Season',
    start_period_nullable="",
    start_range_nullable="",
    team_id=1610612739,
    vs_conference_nullable="",
    vs_division_nullable="",
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

## VideoEvents

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/videoevents.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/videoevents?GameEventID=0&GameID=0021700807`

```python
from nba_api.stats.endpoints import videoevents
endpoint = videoevents.VideoEvents(
    game_event_id=0,
    game_id='0021700807',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

## VideoStatus

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/videostatus.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/videostatus?GameDate=2020-08-16&LeagueID=00`

```python
from nba_api.stats.endpoints import videostatus
endpoint = videostatus.VideoStatus(
    game_date='2020-08-16',
    league_id='00',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- VideoStatus (`video_status`): GAME_ID, GAME_DATE, VISITOR_TEAM_ID, VISITOR_TEAM_CITY, VISITOR_TEAM_NAME, VISITOR_TEAM_ABBREVIATION, HOME_TEAM_ID, HOME_TEAM_CITY, HOME_TEAM_NAME, HOME_TEAM_ABBREVIATION, GAME_STATUS, GAME_STATUS_TEXT, IS_AVAILABLE, PT_XYZ_AVAILABLE

## WinProbabilityPBP

- Doc: `api_docs/nba_api_docs/docs/nba_api/stats/endpoints/winprobabilitypbp.md`
- API family: `stats`
- Valid URL: `https://stats.nba.com/stats/winprobabilitypbp?GameID=0021700807&RunType=each+second`

```python
from nba_api.stats.endpoints import winprobabilitypbp
endpoint = winprobabilitypbp.WinProbabilityPBP(
    game_id='0021700807',
    run_type='each second',
)
data_frames = endpoint.get_data_frames()
for idx, df in enumerate(data_frames):
    print(f'dataset[{idx}] shape={df.shape}')
    print(df.columns.tolist())
```

Documented response structure:

- GameInfo (`game_info`): GAME_ID, GAME_DATE, HOME_TEAM_ID, HOME_TEAM_ABR, HOME_TEAM_PTS, VISITOR_TEAM_ID, VISITOR_TEAM_ABR, VISITOR_TEAM_PTS
- WinProbPBP (`win_prob_p_bp`): GAME_ID, EVENT_NUM, HOME_PCT, VISITOR_PCT, HOME_PTS, VISITOR_PTS, HOME_SCORE_MARGIN, PERIOD, SECONDS_REMAINING, HOME_POSS_IND, HOME_G, DESCRIPTION, LOCATION, PCTIMESTRING, ISVISIBLE
