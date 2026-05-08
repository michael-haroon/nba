#!/usr/bin/env python3
"""Build sample calls and expected response structure for ESPN basketball docs.

This mirrors the NBA helper, but ESPN's docs are organized by endpoint families
and resource groups instead of one markdown file per endpoint. The script reads
the basketball-facing docs and reconstructs sample requests plus related schema
notes from `response_schemas.md`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DOCS_ROOT = ROOT / "docs"
BASKETBALL_DOC = DOCS_ROOT / "sports" / "basketball.md"
GLOBAL_DOC = DOCS_ROOT / "sports" / "_global.md"
SCHEMAS_DOC = DOCS_ROOT / "response_schemas.md"

SAMPLE_VALUES = {
    "{sport}": "basketball",
    "{league}": "nba",
    "{year}": "2025",
    "{season}": "2025",
    "{teamId}": "13",
    "{team}": "13",
    "{event}": "401765432",
    "{EVENT_ID}": "401765432",
    "{competition}": "401765432",
    "{compId}": "401765432",
    "{competitor}": "13",
    "{athleteId}": "3136776",
    "{athlete}": "3136776",
    "{coachId}": "6010",
    "{tournamentId}": "22",
    "{iteration}": "1",
    "{group}": "7",
    "{play}": "4017654340001",
    "{playId}": "4017654340001",
    "{provider}": "41",
    "{sourceId}": "41",
    "{rankingTypeId}": "0",
    "{opponentId}": "3136776",
}

COMMON_PARAM_VALUES = {
    "page": 1,
    "limit": 25,
    "lang": "en",
    "region": "us",
    "dates": "20250320",
    "date": "2025-03-15",
    "season": 2025,
    "year": 2025,
    "week": 1,
    "group": 7,
    "types": 2,
    "type": 2,
    "period": 1,
    "provider.priority": 1,
    "sort": "asc",
    "event": "401765432",
    "eventId": "401765432",
    "team": 13,
    "teamId": 13,
    "athleteId": 3136776,
    "qualified": "true",
    "active": "true",
    "seasontype": 2,
    "seasonType": 2,
    "seasonTypeId": 2,
    "utcOffset": -7,
}

SCHEMA_TITLE_MAP = {
    "scoreboard": "Scoreboard",
    "teams": "Teams",
    "teams/{id}/roster": "Team Roster",
    "teams/{id}/injuries": "Team Injuries",
    "injuries": "League-wide Injuries",
    "summary?event={id}": "Game Summary",
    "standings": "Standings",
    "statistics/byathlete": "Statistics by Athlete",
    "athletes/{id}/overview": "Athlete Overview",
    "athletes/{id}/stats": "Athlete Stats",
    "athletes/{id}/gamelog": "Athlete Gamelog",
    "athletes/{id}/splits": "Athlete Splits",
    "odds": "Betting Odds",
    "probabilities": "Win Probabilities",
}


def python_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    return repr(value)


def fill_placeholders(text: str) -> str:
    rendered = text
    if "teams/{id}" in rendered or "/teams/{id}/" in rendered:
        rendered = rendered.replace("{id}", "13")
    elif "athletes/{id}" in rendered or "/athletes/{id}/" in rendered:
        rendered = rendered.replace("{id}", "3136776")
    elif "summary?event={id}" in rendered or "/events/{id}" in rendered:
        rendered = rendered.replace("{id}", "401765432")
    else:
        rendered = rendered.replace("{id}", "401765432")
    for key, value in SAMPLE_VALUES.items():
        rendered = rendered.replace(key, value)
    return rendered


def parse_table(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if "---" in stripped:
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if not parts or parts[0] == "Endpoint":
            continue
        rows.append(parts)
    return rows


def parse_section_tables(text: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    section = None
    in_api_endpoints = False
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## API Endpoints"):
            in_api_endpoints = True
            i += 1
            continue
        if in_api_endpoints and line.startswith("## ") and line != "## API Endpoints":
            break
        if in_api_endpoints and line.startswith("### "):
            section = line[4:].strip()
            i += 1
            table_lines: list[str] = []
            while i < len(lines):
                current = lines[i]
                if current.startswith("### ") or current.startswith("## "):
                    break
                table_lines.append(current)
                i += 1
            for row in parse_table("\n".join(table_lines)):
                if len(row) < 3:
                    continue
                specs.append(
                    {
                        "name": row[1].strip("`"),
                        "url_pattern": row[0].strip("`"),
                        "query_params": [
                            part.strip("` ")
                            for part in row[2].split(",")
                            if part.strip()
                        ],
                        "doc_path": str(BASKETBALL_DOC.relative_to(ROOT)),
                        "section": section,
                        "api_family": "core-v2",
                        "kind": "table",
                    }
                )
            continue
        i += 1
    return specs


def parse_v3_table(text: str) -> list[dict[str, Any]]:
    block = text.split("## V3 Endpoints", 1)[1].split("## Site API Endpoints", 1)[0]
    specs: list[dict[str, Any]] = []
    for row in parse_table(block):
        if len(row) < 3:
            continue
        specs.append(
            {
                "name": row[1].strip("`"),
                "url_pattern": row[0].strip("`"),
                "query_params": [
                    part.strip("` ")
                    for part in row[2].split(",")
                    if part.strip()
                ],
                "doc_path": str(BASKETBALL_DOC.relative_to(ROOT)),
                "section": "V3 Endpoints",
                "api_family": "core-v3",
                "kind": "table",
            }
        )
    return specs


def parse_site_resources(text: str) -> list[dict[str, Any]]:
    block = text.split("## Site API Endpoints", 1)[1].split("## CDN Game Data", 1)[0]
    base_pattern = "https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/{resource}"
    specs: list[dict[str, Any]] = []
    for row in parse_table(block):
        if len(row) < 2:
            continue
        resource = row[0].strip("`")
        description = row[1]
        url_pattern = base_pattern.replace("{resource}", resource)
        if resource == "standings":
            url_pattern = "https://site.api.espn.com/apis/v2/sports/basketball/{league}/standings"
        specs.append(
            {
                "name": f"site:{resource}",
                "url_pattern": url_pattern,
                "query_params": [],
                "doc_path": str(BASKETBALL_DOC.relative_to(ROOT)),
                "section": "Site API Endpoints",
                "api_family": "site-v2",
                "kind": "site-resource",
                "resource": resource,
                "note": description,
            }
        )
    return specs


def parse_url_examples(block: str, section: str, api_family: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    lines = block.splitlines()
    pending_comment = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            pending_comment = stripped.lstrip("# ").strip()
            continue
        match = re.search(r'curl "([^"]+)"', stripped)
        if not match:
            match = re.search(r"GET\s+(https?://\S+)", stripped)
        if not match:
            continue
        url = match.group(1)
        name = pending_comment or url.rsplit("/", 1)[-1]
        specs.append(
            {
                "name": name,
                "url_pattern": url,
                "query_params": [],
                "doc_path": str(BASKETBALL_DOC.relative_to(ROOT)),
                "section": section,
                "api_family": api_family,
                "kind": "curl-example",
            }
        )
        pending_comment = None
    return specs


def parse_specialized(text: str) -> list[dict[str, Any]]:
    block = text.split("## Specialized Endpoints", 1)[1].split("## Example API Calls", 1)[0]
    specs: list[dict[str, Any]] = []
    current = None
    current_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("### "):
            if current and current_lines:
                specs.extend(parse_url_examples("\n".join(current_lines), current, "specialized"))
            current = line[4:].strip()
            current_lines = []
            continue
        current_lines.append(line)
    if current and current_lines:
        specs.extend(parse_url_examples("\n".join(current_lines), current, "specialized"))
    return specs


def parse_global_quick_reference(text: str) -> list[dict[str, Any]]:
    block = text.split("## 🚀 Quick Reference", 1)[1].split("## V2 Global Endpoints", 1)[0]
    specs: list[dict[str, Any]] = []
    section = None
    collected: list[str] = []
    for line in block.splitlines():
        if line.startswith("### "):
            if section and collected:
                specs.extend(parse_url_examples("\n".join(collected), f"Global: {section}", "global"))
            section = line[4:].strip()
            collected = []
            continue
        collected.append(line)
    if section and collected:
        specs.extend(parse_url_examples("\n".join(collected), f"Global: {section}", "global"))
    for spec in specs:
        spec["doc_path"] = str(GLOBAL_DOC.relative_to(ROOT))
    return specs


def parse_schema_examples(text: str) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            title = line[3:].strip()
            short_title = re.split(r"\s+\(`", title, maxsplit=1)[0].strip()
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```json"):
                if lines[i].startswith("## "):
                    break
                i += 1
            if i < len(lines) and lines[i].strip().startswith("```json"):
                i += 1
                block_lines: list[str] = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    block_lines.append(lines[i])
                    i += 1
                raw = "\n".join(block_lines)
                top_level_keys: list[str] = []
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        top_level_keys = list(parsed.keys())
                except json.JSONDecodeError:
                    depth = 0
                    for raw_line in raw.splitlines():
                        stripped = raw_line.strip()
                        if "{" in stripped:
                            depth += stripped.count("{")
                        if depth == 1:
                            key_match = re.match(r'"([^"]+)":', stripped)
                            if key_match:
                                top_level_keys.append(key_match.group(1))
                        if "}" in stripped:
                            depth -= stripped.count("}")
                schemas[short_title] = {
                    "title": short_title,
                    "full_title": title,
                    "top_level_keys": top_level_keys,
                    "raw": raw,
                }
        i += 1
    return schemas


def choose_schema_title(spec: dict[str, Any]) -> str | None:
    resource = spec.get("resource")
    if resource and resource in SCHEMA_TITLE_MAP:
        return SCHEMA_TITLE_MAP[resource]
    url = spec["url_pattern"]
    for needle, title in SCHEMA_TITLE_MAP.items():
        if needle in url:
            return title
    if "predictor" in url or "probabilities" in url:
        return "Win Probabilities"
    return None


def build_sample_params(params: list[str]) -> dict[str, Any]:
    seen: set[str] = set()
    sample: dict[str, Any] = {}
    for param in params:
        key = param.strip()
        if not key or key == "—" or key in seen:
            continue
        seen.add(key)
        if key in COMMON_PARAM_VALUES:
            sample[key] = COMMON_PARAM_VALUES[key]
    return sample


def render_url_pattern(url_pattern: str) -> str:
    return fill_placeholders(url_pattern)


def build_sample_code(spec: dict[str, Any]) -> str:
    url = render_url_pattern(spec["url_pattern"])
    params = build_sample_params(spec.get("query_params", []))
    lines = ["import requests", "", f"url = {python_literal(url)}"]
    if params:
        lines.append("params = {")
        for key, value in params.items():
            lines.append(f"    {python_literal(key)}: {python_literal(value)},")
        lines.append("}")
        lines.append("response = requests.get(url, params=params, timeout=30)")
    else:
        lines.append("response = requests.get(url, timeout=30)")
    lines.extend(
        [
            "response.raise_for_status()",
            "data = response.json()",
            "print(type(data).__name__)",
            "if isinstance(data, dict):",
            "    print(list(data.keys())[:20])",
            "elif isinstance(data, list):",
            "    print(f'items={len(data)}')",
        ]
    )
    return "\n".join(lines)


def normalize_specs(specs: list[dict[str, Any]], schemas: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for spec in specs:
        schema_title = choose_schema_title(spec)
        schema = schemas.get(schema_title) if schema_title else None
        normalized.append(
            {
                **spec,
                "sample_url": render_url_pattern(spec["url_pattern"]),
                "sample_params": build_sample_params(spec.get("query_params", [])),
                "sample_code": build_sample_code(spec),
                "schema_title": schema_title,
                "schema_top_level_keys": schema.get("top_level_keys", []) if schema else [],
            }
        )
    return normalized


def build_specs(include_global: bool = False) -> list[dict[str, Any]]:
    basketball_text = BASKETBALL_DOC.read_text()
    schemas = parse_schema_examples(SCHEMAS_DOC.read_text())

    specs: list[dict[str, Any]] = []
    specs.extend(parse_section_tables(basketball_text))
    specs.extend(parse_v3_table(basketball_text))
    specs.extend(parse_site_resources(basketball_text))
    cdn_block = basketball_text.split("## CDN Game Data", 1)[1].split("## Athlete Data (common/v3)", 1)[0]
    athlete_block = basketball_text.split("## Athlete Data (common/v3)", 1)[1].split("## Specialized Endpoints", 1)[0]
    example_block = basketball_text.split("## Example API Calls", 1)[1]
    specs.extend(parse_url_examples(cdn_block, "CDN Game Data", "cdn"))
    specs.extend(parse_url_examples(athlete_block, "Athlete Data (common/v3)", "common-v3"))
    specs.extend(parse_specialized(basketball_text))
    specs.extend(parse_url_examples(example_block, "Example API Calls", "example"))

    if include_global:
        specs.extend(parse_global_quick_reference(GLOBAL_DOC.read_text()))

    return normalize_specs(specs, schemas)


def emit_markdown(specs: list[dict[str, Any]], include_global: bool) -> str:
    title = "# ESPN Endpoint Samples"
    scope = "basketball docs plus global quick-reference" if include_global else "basketball docs"
    parts = [
        title,
        "",
        f"Generated from the ESPN {scope} in `docs/`.",
        "",
    ]
    for spec in specs:
        parts.append(f"## {spec['name']}")
        parts.append("")
        parts.append(f"- Doc: `{spec['doc_path']}`")
        parts.append(f"- Section: `{spec['section']}`")
        parts.append(f"- API family: `{spec['api_family']}`")
        parts.append(f"- URL pattern: `{spec['url_pattern']}`")
        parts.append(f"- Sample URL: `{spec['sample_url']}`")
        if spec.get("query_params"):
            parts.append(f"- Query params: `{', '.join(spec['query_params'])}`")
        if spec.get("note"):
            parts.append(f"- Note: {spec['note']}")
        if spec.get("schema_title"):
            parts.append(f"- Related schema: `{spec['schema_title']}`")
        if spec.get("schema_top_level_keys"):
            parts.append(
                f"- Documented top-level keys: `{', '.join(spec['schema_top_level_keys'])}`"
            )
        parts.append("")
        parts.append("```python")
        parts.append(spec["sample_code"])
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--include-global", action="store_true")
    parser.add_argument(
        "--output",
        help="Custom filename. If omitted, uses 'structure_report'.",
    )
    args = parser.parse_args()

    specs = build_specs(include_global=args.include_global)
    rendered = (
        emit_markdown(specs, include_global=args.include_global)
        if args.format == "markdown"
        else json.dumps(specs, indent=2)
    )

    filename = args.output if args.output else f"structure_report.{args.format}"
    full_path = ROOT / filename
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(rendered)
    print(f"File successfully saved to: {full_path}")


if __name__ == "__main__":
    main()
