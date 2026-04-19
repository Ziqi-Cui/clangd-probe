from __future__ import annotations

from pathlib import Path

from ..output import CommandResult
from ..resolve import parse_location, resolve_target
from .common import backend_factory, prepare_semantic_context, semantic_symbol_search, sort_locations


def run(args, context):
    preflight = prepare_semantic_context("def", args, context)
    if preflight is not None:
        return preflight

    lookup_target = None
    location_target = parse_location(args.target)
    initial_file = location_target["path"] if location_target is not None else None
    if location_target is not None:
        target = location_target
        if not Path(target["path"]).exists():
            return CommandResult(
                command="def",
                status="error",
                diagnostics=[
                    {
                        "error_kind": "setup_failure",
                        "message": f"source file does not exist: {target['path']}",
                        "next_step": "Pass an existing file path or resolve the correct repository root first.",
                    }
                ],
            )
        lookup_target = target
    try:
        with backend_factory(context, initial_file=initial_file) as backend:
            lookup = (lambda query: semantic_symbol_search(context, backend, query)) if getattr(backend, "supports_workspace_symbols", False) or hasattr(backend, "document_symbols") else None
            if lookup_target is None:
                resolved = resolve_target(args.target, symbol_lookup=lookup)
                if resolved.status != "ok":
                    return CommandResult(command="def", status=resolved.status, results=resolved.results, diagnostics=resolved.diagnostics)
                target = resolved.results[0]
            else:
                target = lookup_target

            if target.get("kind") == "location":
                results = backend.definition(target["path"], target["line"], target["column"])
            else:
                results = [target]
    except RuntimeError as exc:
        return CommandResult(
            command="def",
            status="error",
            diagnostics=[{"error_kind": "setup_failure", "message": str(exc), "next_step": "Install clangd or expose it on PATH."}],
        )

    results = sort_locations(results)
    return CommandResult(command="def", status="ok" if results else "no_results", results=results)
