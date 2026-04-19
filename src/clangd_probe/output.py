from __future__ import annotations

import json
from dataclasses import dataclass, field

from .context import ExecutionContext

STATUS_VALUES = {"ok", "no_results", "ambiguous", "unsupported", "error"}
ERROR_KINDS = {
    "setup_failure",
    "discovery_failure",
    "parse_failure",
    "internal_failure",
}


@dataclass
class CommandResult:
    command: str
    status: str = "ok"
    results: list[object] = field(default_factory=list)
    warnings: list[object] = field(default_factory=list)
    diagnostics: list[object] = field(default_factory=list)
    truncated: bool = False

    def to_envelope(self, context: ExecutionContext) -> dict[str, object]:
        if self.status not in STATUS_VALUES:
            raise ValueError(f"unsupported status {self.status!r}")
        return {
            "command": self.command,
            "status": self.status,
            "project_root": context.project_root,
            "active_compdb": context.active_compdb,
            "active_profile": context.active_profile,
            "adapter": context.adapter,
            "backend": context.backend,
            "results": self.results,
            "warnings": self.warnings,
            "diagnostics": self.diagnostics,
            "truncated": self.truncated,
        }


def render_json(result: CommandResult, context: ExecutionContext) -> str:
    return json.dumps(result.to_envelope(context), indent=2, sort_keys=True)


def render_human(result: CommandResult, context: ExecutionContext) -> str:
    lines = [
        f"command: {result.command}",
        f"status: {result.status}",
        f"project_root: {context.project_root or '-'}",
        f"active_compdb: {context.active_compdb or '-'}",
        f"active_profile: {context.active_profile or '-'}",
        f"adapter: {context.adapter}",
        f"backend: {context.backend}",
    ]
    for warning in result.warnings:
        lines.append(f"warning: {render_message(warning)}")
    for diagnostic in result.diagnostics:
        lines.append(f"diagnostic: {render_message(diagnostic)}")
    return "\n".join(lines)


def parse_failure_result(command: str, message: str) -> CommandResult:
    return CommandResult(
        command=command,
        status="error",
        diagnostics=[
            {
                "error_kind": "parse_failure",
                "message": message,
            }
        ],
    )


def render_message(entry: object) -> str:
    if isinstance(entry, dict):
        message = entry.get("message")
        if isinstance(message, str) and message:
            return message
        error_kind = entry.get("error_kind")
        if isinstance(error_kind, str) and error_kind:
            return error_kind
        return json.dumps(entry, sort_keys=True)
    return str(entry)
