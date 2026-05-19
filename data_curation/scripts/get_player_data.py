"""
Endpoints and why we want them:

  PlayByPlayV3 — raw event log per game (requires
  GameID).
    - Columns: period, clock, playerName, actionType,
    scoreHome, scoreAway, shotResult, shotDistance
    - Gives you the full sequence of events with
    timestamps — best for constructing in-game timelines

  BoxScore endpoints (per GameID, not historical bulk):
    - BoxScoreTraditionalV3 — standard stats per player
    per game
    - BoxScoreAdvancedV3 — offensiveRating,
    defensiveRating, usagePercentage, PIE, netRating,
    trueShootingPercentage, pace, possessions
    - BoxScorePlayerTrackV3 — tracking: distance, touches,
    passes, contestedFGAttempted, reboundChances
    
"""