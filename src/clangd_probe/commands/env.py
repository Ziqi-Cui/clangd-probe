from __future__ import annotations

import shutil

from ..discovery import discover
from ..output import CommandResult


def find_clangd():
    return shutil.which("clangd")


def run(args, context) -> CommandResult:
    discovery = discover(
        project=getattr(args, "project", None),
        compdb=getattr(args, "compdb", None),
        profile=getattr(args, "profile", None),
    )
    context.apply_discovery(discovery)

    clangd_path = find_clangd()
    results = [
        {
            "kind": "environment",
            "project_root": context.project_root,
            "active_compdb": context.active_compdb,
            "active_profile": context.active_profile,
            "adapter": context.adapter,
            "backend": context.backend,
            "verbose": context.verbose,
            "limit": context.limit,
            "clangd_available": clangd_path is not None,
            "clangd_path": clangd_path,
        }
    ]

    return CommandResult(
        command="env",
        status=discovery.status,
        results=results,
        warnings=discovery.warnings,
        diagnostics=discovery.diagnostics,
    )
