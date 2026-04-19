from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


LOCATION_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::(?P<column>\d+))?$")


@dataclass
class ResolutionResult:
    status: str
    results: list[dict[str, object]] = field(default_factory=list)
    diagnostics: list[dict[str, str]] = field(default_factory=list)


def resolve_target(target: str, symbol_lookup=None) -> ResolutionResult:
    location = parse_location(target)
    if location is not None:
        return ResolutionResult(status="ok", results=[location])

    if symbol_lookup is None:
        return ResolutionResult(
            status="unsupported",
            diagnostics=[
                {
                    "error_kind": "setup_failure",
                    "message": "symbol-form resolution is unavailable in the active backend",
                }
            ],
        )

    matches = list(symbol_lookup(target))
    if not matches:
        return ResolutionResult(status="no_results")

    ranked = rank_matches(target, matches)
    top_score = ranked[0][0]
    top_matches = [match for score, match in ranked if score == top_score]

    if len(top_matches) > 1:
        return ResolutionResult(status="ambiguous", results=top_matches)

    return ResolutionResult(status="ok", results=[ranked[0][1]])


def parse_location(target: str):
    match = LOCATION_RE.match(target)
    if not match:
        return None

    path = Path(match.group("path")).resolve()
    column = match.group("column")
    return {
        "kind": "location",
        "path": str(path),
        "line": int(match.group("line")),
        "column": int(column) if column is not None else 1,
    }


def rank_matches(target: str, matches):
    ranked = []
    for match in matches:
        ranked.append((match_score(target, match), match))
    ranked.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("qualified_name", "")),
            str(item[1].get("path", "")),
            int(item[1].get("line", 0)),
            int(item[1].get("column", 0)),
        )
    )
    return ranked


def match_score(target: str, match: dict[str, object]) -> int:
    qualified_name = str(match.get("qualified_name", ""))
    name = str(match.get("name", ""))

    if qualified_name == target:
        return 300
    if name == target:
        return 200
    if qualified_name.endswith(target):
        return 150
    if name.startswith(target):
        return 100
    if target in qualified_name:
        return 50
    return 0

