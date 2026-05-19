#!/usr/bin/env python3
"""Build sample calls and expected output structure for a set of NBA API endpoints.

This script is docs-driven: it parses the markdown files under
`nba_api_docs/docs` and reconstructs a sample Python call plus the documented
response structure for each endpoint.

It is useful even when `nba_api` is not installed locally, because it does not
make any HTTP requests by default.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse


ROOT = Path(__file__).resolve().parent
DOCS_ROOT_CANDIDATES = [
    ROOT / "api_docs" / "nba_api_docs" / "docs",
    ROOT / "nba_api_docs" / "docs",
]
DOCS_ROOT = next((path for path in DOCS_ROOT_CANDIDATES if path.exists()), DOCS_ROOT_CANDIDATES[0])
STATS_DOCS = DOCS_ROOT / "nba_api" / "stats" / "endpoints"
LIVE_DOCS = DOCS_ROOT / "nba_api" / "live" / "endpoints"

ENDPOINTS = [
    "AllTimeLeadersGrids",
    "AssistLeaders",
    "AssistTracker",
    "BoxScoreAdvancedV2",
    "BoxScoreFourFactorsV2",
    "BoxScoreMatchupsV3",
    "BoxScoreMiscV2",
    "BoxScoreScoringV2",
    "BoxScoreSimilarityScore",
    "BoxScoreSummaryV2",
    "BoxScoreTraditionalV2",
    "BoxScoreUsageV2",
    "CommonAllPlayers",
    "CommonPlayerInfo",
    "CommonPlayoffSeries",
    "CommonTeamRoster",
    "CommonTeamYears",
    "CumeStatsPlayer",
    "CumeStatsPlayerGames",
    "CumeStatsTeam",
    "CumeStatsTeamGames",
    "DefenseHub",
    "DraftBoard",
    "DraftCombineDrillResults",
    "DraftCombineNonStationaryShooting",
    "DraftCombinePlayerAnthro",
    "DraftCombineSpotShooting",
    "DraftCombineStats",
    "DraftHistory",
    "FantasyWidget",
    "FranchiseHistory",
    "FranchiseLeaders",
    "FranchisePlayers",
    "GameRotation",
    "GLAlumBoxScoreSimilarityScore",
    "HomePageLeaders",
    "HomePageV2",
    "HustleStatsBoxScore",
    "InfographicFanDuelPlayer",
    "LeadersTiles",
    "LeagueDashLineups",
    "LeagueDashPlayerBioStats",
    "LeagueDashPlayerClutch",
    "LeagueDashOppPtShot",
    "LeagueDashPlayerPtShot",
    "LeagueDashPlayerShotLocations",
    "LeagueDashPlayerStats",
    "LeagueDashPtDefend",
    "LeagueDashPtStats",
    "LeagueDashPtTeamDefend",
    "LeagueDashTeamClutch",
    "LeagueDashTeamPtShot",
    "LeagueDashTeamShotLocations",
    "LeagueDashTeamStats",
    "LeagueHustleStatsPlayer",
    "LeagueHustleStatsTeam",
    "LeagueGameFinder",
    "LeagueGameLog",
    "LeagueLeaders",
    "LeagueLineupViz",
    "LeaguePlayerOnDetails",
    "LeagueSeasonMatchups",
    "LeagueStandings",
    "LeagueStandingsV3",
    "MatchupsRollup",
    "Odds",
    "PlayByPlay",
    "PlayByPlayV2",
    "PlayerAwards",
    "PlayerCareerByCollege",
    "PlayerCareerByCollegeRollup",
    "PlayerCareerStats",
    "PlayerCompare",
    "PlayerDashPtPass",
    "PlayerDashPtReb",
    "PlayerDashPtShotDefend",
    "PlayerDashPtShots",
    "PlayerDashboardByClutch",
    "PlayerDashboardByGameSplits",
    "PlayerDashboardByGeneralSplits",
    "PlayerDashboardByLastNGames",
    "PlayerDashboardByShootingSplits",
    "PlayerDashboardByTeamPerformance",
    "PlayerDashboardByYearOverYear",
    "PlayerEstimatedMetrics",
    "PlayerFantasyProfileBarGraph",
    "PlayerGameLog",
    "PlayerGameLogs",
    "PlayerGameStreakFinder",
    "PlayerNextNGames",
    "PlayerProfileV2",
    "PlayerVsPlayer",
    "PlayoffPicture",
    "ScoreboardV2",
    "ShotChartDetail",
    "ShotChartLeagueWide",
    "ShotChartLineupDetail",
    "SynergyPlayTypes",
    "TeamAndPlayersVsPlayers",
    "TeamDashLineups",
    "TeamDashPtPass",
    "TeamDashPtReb",
    "TeamDashPtShots",
    "TeamDashboardByGeneralSplits",
    "TeamDashboardByShootingSplits",
    "TeamDetails",
    "TeamEstimatedMetrics",
    "TeamGameStreakFinder",
    "TeamInfoCommon",
    "TeamPlayerDashboard",
    "TeamPlayerOnOffDetails",
    "TeamPlayerOnOffSummary",
    "TeamVsPlayer",
    "TeamYearByYearStats",
    "VideoDetails",
    "VideoDetailsAsset",
    "VideoEvents",
    "VideoStatus",
    "WinProbabilityPBP",
]


def find_doc_path(endpoint_name: str) -> tuple[str, Path | None, str | None]:
    slug = endpoint_name.lower()
    stats_path = STATS_DOCS / f"{slug}.md"
    live_path = LIVE_DOCS / f"{slug}.md"

    if endpoint_name == "PlayByPlay":
        # Prefer the stats endpoint because the user's list separately includes
        # PlayByPlayV2 and the stats docs align with the rest of this sampler.
        if stats_path.exists():
            return "stats", stats_path, "Live PlayByPlay docs also exist."
        if live_path.exists():
            return "live", live_path, None

    if stats_path.exists():
        return "stats", stats_path, None
    if live_path.exists():
        return "live", live_path, None
    return "missing", None, None


def parse_parameter_rows(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    in_parameters = False
    for line in text.splitlines():
        if line.startswith("## Parameters"):
            in_parameters = True
            continue
        if in_parameters and line.startswith("## "):
            break
        if not in_parameters or "|" not in line:
            continue
        if "API Parameter Name" in line or "------------" in line or "---" in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        api_name = parts[1].strip()
        api_name = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", api_name)
        api_name = re.sub(r"[\[\]_*`]", "", api_name).strip()
        python_name = parts[2].strip(" `")
        if api_name and python_name:
            rows.append((api_name, python_name))
    return rows


def parse_valid_url(text: str) -> str | None:
    match = re.search(r"##### Valid URL\s*>+\[(https?://[^\]]+)\]", text, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def parse_data_sets(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    data_sets: list[dict[str, Any]] = []
    in_data_sets = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## Data Sets"):
            in_data_sets = True
            i += 1
            continue
        if in_data_sets and line.startswith("## JSON"):
            break
        if in_data_sets and line.startswith("#### "):
            header = line[5:].strip()
            if "`" in header:
                title, attr = header.split("`", 1)
                data_set_name = title.strip()
                attribute_name = attr.split("`", 1)[0].strip()
            else:
                data_set_name = header
                attribute_name = None

            columns: list[str] = []
            i += 1
            if i < len(lines) and lines[i].strip().startswith("```"):
                i += 1
                block_lines: list[str] = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    block_lines.append(lines[i])
                    i += 1
                block_text = "\n".join(block_lines).strip()
                try:
                    columns = json.loads(block_text.replace("'", '"'))
                except json.JSONDecodeError:
                    stripped = block_text.strip()
                    if stripped.startswith("[") and stripped.endswith("]"):
                        inner = stripped[1:-1].strip()
                        if inner:
                            columns = [
                                item.strip().strip("'").strip('"')
                                for item in inner.split(",")
                            ]
                        else:
                            columns = []
            data_sets.append(
                {
                    "data_set_name": data_set_name,
                    "attribute_name": attribute_name,
                    "columns": columns,
                }
            )
        i += 1
    return data_sets


def python_literal(value: str) -> str:
    if value == "":
        return '""'
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered.capitalize()
    if re.fullmatch(r"-?\d+", value):
        if len(value) > 1 and value.lstrip("-").startswith("0"):
            return repr(value)
        return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        return value
    return repr(value)


def build_sample_kwargs(valid_url: str | None, parameter_rows: list[tuple[str, str]]) -> dict[str, str]:
    if not valid_url:
        return {}
    query = dict(parse_qsl(urlparse(valid_url).query, keep_blank_values=True))
    python_map = {api_name: py_name for api_name, py_name in parameter_rows}
    kwargs: dict[str, str] = {}
    for api_name, value in query.items():
        py_name = python_map.get(api_name)
        if py_name:
            kwargs[py_name] = python_literal(value)
    return kwargs


def build_import_snippet(endpoint_name: str, doc_kind: str) -> str:
    module_name = endpoint_name.lower()
    if doc_kind == "live":
        return (
            f"from nba_api.live.nba.endpoints import {module_name}\n"
            f"endpoint = {module_name}.{endpoint_name}("
        )
    return (
        f"from nba_api.stats.endpoints import {module_name}\n"
        f"endpoint = {module_name}.{endpoint_name}("
    )


def build_sample_code(endpoint_name: str, doc_kind: str, kwargs: dict[str, str]) -> str:
    prefix = build_import_snippet(endpoint_name, doc_kind)
    if kwargs:
        args = ",\n    ".join(f"{key}={value}" for key, value in kwargs.items())
        body = f"\n    {args},\n)"
    else:
        body = ")"

    if doc_kind == "live":
        tail = (
            "\nresponse = endpoint.get_dict()\n"
            "print(type(response).__name__)\n"
            "print(response.keys())"
        )
    else:
        tail = (
            "\ndata_frames = endpoint.get_data_frames()\n"
            "for idx, df in enumerate(data_frames):\n"
            "    print(f'dataset[{idx}] shape={df.shape}')\n"
            "    print(df.columns.tolist())"
        )
    return prefix + body + tail


def parse_doc(endpoint_name: str) -> dict[str, Any]:
    doc_kind, path, note = find_doc_path(endpoint_name)
    if path is None:
        return {
            "endpoint": endpoint_name,
            "doc_kind": "missing",
            "doc_path": None,
            "sample_code": None,
            "valid_url": None,
            "data_sets": [],
            "note": "No matching markdown doc found in this repo.",
        }

    text = path.read_text()
    parameter_rows = parse_parameter_rows(text)
    valid_url = parse_valid_url(text)
    kwargs = build_sample_kwargs(valid_url, parameter_rows)
    data_sets = parse_data_sets(text)

    return {
        "endpoint": endpoint_name,
        "doc_kind": doc_kind,
        "doc_path": str(path.relative_to(ROOT)),
        "valid_url": valid_url,
        "sample_kwargs": kwargs,
        "sample_code": build_sample_code(endpoint_name, doc_kind, kwargs),
        "data_sets": data_sets,
        "note": note,
    }


def build_specs() -> list[dict[str, Any]]:
    return [parse_doc(endpoint_name) for endpoint_name in ENDPOINTS]


def emit_markdown(specs: list[dict[str, Any]]) -> str:
    parts = [
        "# NBA Endpoint Samples",
        "",
        f"Generated from the markdown docs in `{DOCS_ROOT.relative_to(ROOT)}`.",
        "",
    ]
    for spec in specs:
        parts.append(f"## {spec['endpoint']}")
        if spec["doc_path"] is None:
            parts.append("")
            parts.append(f"- Status: missing docs")
            parts.append(f"- Note: {spec['note']}")
            parts.append("")
            continue

        parts.append("")
        parts.append(f"- Doc: `{spec['doc_path']}`")
        parts.append(f"- API family: `{spec['doc_kind']}`")
        if spec.get("note"):
            parts.append(f"- Note: {spec['note']}")
        if spec.get("valid_url"):
            parts.append(f"- Valid URL: `{spec['valid_url']}`")
        parts.append("")
        parts.append("```python")
        parts.append(spec["sample_code"])
        parts.append("```")
        parts.append("")
        if spec["data_sets"]:
            parts.append("Documented response structure:")
            parts.append("")
            for data_set in spec["data_sets"]:
                label = data_set["data_set_name"]
                if data_set["attribute_name"]:
                    label += f" (`{data_set['attribute_name']}`)"
                if data_set["columns"]:
                    cols = ", ".join(
                        item if isinstance(item, str) else json.dumps(item, sort_keys=True)
                        for item in data_set["columns"]
                    )
                else:
                    cols = "(empty)"
                parts.append(f"- {label}: {cols}")
            parts.append("")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format.",
    )
    # Keeping --output as optional; if not provided, it uses the default path
    parser.add_argument(
        "--output",
        help="Custom filename. If omitted, uses 'structure_report'.",
    )
    args = parser.parse_args()

    # 1. Define the absolute or relative target directory
    # Use .resolve() to ensure the path is absolute relative to your script
    target_dir = Path("nba/api_docs/nba_api_docs").resolve()

    specs = build_specs()
    rendered = (
        emit_markdown(specs)
        if args.format == "markdown"
        else json.dumps(specs, indent=2)
    )

    # 2. Determine the filename
    filename = args.output if args.output else f"structure_report.{args.format}"
    
    # 3. Join the directory with the filename
    full_path = target_dir / filename

    # 4. Create the directory tree and write
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(rendered)
    
    print(f"File successfully saved to: {full_path}")

if __name__ == "__main__":
    main()