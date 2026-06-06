# CLAUDE.md

## Repository & Project Overview
*   **Path:** `/Users/michaelharoon/Projects/prediction_markets/nba`
*   **Objective:** Automated trade execution system for NBA markets on Kalshi.
*   **Methodology:** Machine learning techniques such as Marcos López de Prado's Financial Machine Learning framework. Note that we are working on sports, so we are only transferring skills since some are not directly applicable.
*   **Project Architecture:** 6 step architecture: data curation, feature analysis, strategy development, backtesting, deployment, and portfolio oversight/risk managment.
*   **Environment:** All execution and development takes place in the Conda environment: `pred`.
* **Claude Requirements:** 
    1) Maintain rigorous documentation after implementing significant structural or logic updates to ensure codebase transparency. The repository currently contains the following core tracking records:
        * `FEATURES.md` – Comprehensive directory of all engineered features.
        * `TARGETS.md` – Detailed definitions and logic for all prediction targets.
        * `README.md` – High-level overview and architectural blueprint of the entire project.
        * `TODOS.md` – Prioritized list of actionable next steps (intended for human writers and review).
        * `data_curation/data/SCHEMA.md` – Complete schema definitions and structural descriptions of all data artifacts.
        * `feature_pipeline/README.md` – Dedicated documentation detailing the data ingestion and transformation pipeline.
        * `strategy/README.md` – Technical specifications and execution details for the strategy module.
    2) Ensure that scripts write to logs for later review.
    3) Always visualize data before making modeling decisions. Every new analysis, assumption, or distributional claim must produce plots (QQ, distribution, calibration, etc.) for human review before code changes are made. The human cannot validate what they cannot see.

Note that we are using a MacBook M1, 8core 16gb ram computer, but we can use AWS EC2 when needed.

---

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- Prove your assumptions and propositions by diving into the code, reasoning thoroughly, and discussing with the human user.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess. Do NOT overwrite existing data or files without asking first.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Records and Documentation

**Keep and regularly update logs of every significant change, input, and output**

Make the project as easy to digest for current and future human review:
- "Add logging" → Send outputs of scripts into a log file. Log the most important information (e.g. timestamp, specific errors, progress bars)
- Record features, targets, schemas, formulas, math logic, and other important architectural, infrastructural, or analytical decisions
- Plot data granularly to show all perspectives and stories to human reviewers

This allows human authors to easily fix Claude mistakes that might go unseen otherwise.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions come before implementation rather than after mistakes, and detailed, non-bloating, human-readable logs and records are made frequently.

---
 
## Feature-specific instructions: LEAKAGE PREVENTION

All features used for prediction MUST come from BEFORE the game date. Never use same-game or post-game data as features.
- Temporal embargo: ratings/stats from day T can only predict the next nearest game
- Purging: cross-validation folds must be purged so that no training data overlaps temporally with test data (PurgedYearKFold handles this)
- Same-game box scores (pts, fgm, offrtg, etc.) are OUTCOMES, not features. Only rolling averages of PRIOR games are valid features.
- When in doubt, ask: "could I know this value BEFORE tipoff?" If no, it's leakage.

---

## Data
Arguably the most important part is to NOT go based off heuristics, guesses, or "best practices" when working with data. Quantify everything rigorously, using proofs and real data. That is, don't guess what the story might be. query the data and see what it says.

---

## Kalshi markets
We are only takers for now. That means we can only post bids and aggress the lowest ask.