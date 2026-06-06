Keys for each LOCAL file (and their respective tsvs/csvs in s3). be sure to remove low quality rows and redundant cols (redundant if and only if the column name and content match another column exactly 100%)

📦 Dataset: AdvBoxScoresAdvPlayoffs (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', 'game_id']      # note that files with these columns have a pattern in MATCH UP that we need to account for: it can take the form ABC @ DEF or ABC VS. DEF
                                                            # also note that game_id was added, so the default key is team+match up+game date
📦 Dataset: AdvBoxScoresAdvPre (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE']

📦 Dataset: AdvBoxScoresAdvRegular (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE']

📦 Dataset: AdvBoxScoresFourFactorsPlayoffs (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', 'game_id']

📦 Dataset: AdvBoxScoresFourFactorsPre (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE']

📦 Dataset: AdvBoxScoresFourFactorsRegular (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE']

📦 Dataset: AdvBoxScoresMiscPlayoffs (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', 'game_id']

📦 Dataset: AdvBoxScoresMiscPre (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE']

📦 Dataset: AdvBoxScoresMiscRegular (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE']

📦 Dataset: AdvBoxScoresScoringPlayoffs (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', 'game_id']

📦 Dataset: AdvBoxScoresScoringPre (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', ]

📦 Dataset: AdvBoxScoresScoringRegular (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', ]

📦 Dataset: AdvBoxScoresTradPlayoffs (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE', 'game_id']

📦 Dataset: AdvBoxScoresTradPre (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE',]

📦 Dataset: AdvBoxScoresTradRegular (.parquet)
   Columns: ['TEAM'+'MATCH UP'+'GAME DATE',]

📦 Dataset: BPI (.parquet)
!!!
-> WARNING: THIS FILE DOES NOT HAVE PROOF OF TIME WHEN THE RATING IS GIVEN! SNAPSHOT TIME IS NOT NECESSARILY RATING TIME! For that reason, I removed it from local, so you can ignore it
!!!
   Columns: ['snapshot_timestamp' plus one of the following: 'team_id', 'team_name', 'team_abbrev']

📦 Dataset: BoxScoresHustleTeam (.parquet)
   Columns: ['gameId' plus one of the following: 'teamId', 'teamName', 'teamTricode', 'teamSlug']

📦 Dataset: GameOfficials (.parquet)
   Columns: ['game_id'+'official_name']

📦 Dataset: GameSummaries (.parquet)
   Columns: ['game_id', 'game_code']

📦 Dataset: MasseyRatings (.parquet)
   Columns: ['game_date'+'team_id']

📦 Dataset: NBAGameIDs (.parquet)
   Columns: ['GAME_ID']

📦 Dataset: NBATeams (.parquet)
   Columns: ['TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME']

📦 Dataset: PlayerStatus (.parquet)
   Columns: ['game_id' plus one of the following: 'player_id', 'player_name']

📦 Dataset: SagarinRatings (.parquet)
   Columns: ['team']

📦 Dataset: TeamQuarterScores (.parquet)
   Columns: ['game_id'+'team_id'+'period_label']

📦 Dataset: nba_arenas_geocoded (.csv)
   Columns: ['team']

📦 Dataset: sync_complete (.parquet)
   Columns: ['game_id']

I think the analysis is easy. getting data that no one has seen before is not. that is hard

note that sync parquet is not a good indicator for files that are synced. we need to add game id keys to all relevant fiels first, standardize columns, then sync easily using difference in gameids
we also need to sync boxscorehustleteam. ideally, the sync script syncs ALL folders for ALL time for ALL data points, but we can't run it safely hitting multipel enpoints simult and back to back without getting banned

the key thing with syncing in the long run is that all actions, taken and not taken and data missed or not missed, must be logged, and that each parquet has different definitions of quality and common mistakes. think and act out the system to make it easier to code it up. This whoole project will get massive and hard to maange. make it easy to digest. Log provenance