from __future__ import annotations

from ..output import CommandResult
from ..resolve import parse_location, resolve_target
from .common import backend_factory, prepare_semantic_context, semantic_symbol_search, sort_locations


def run(args, context):
    preflight = prepare_semantic_context("refs", args, context)
    if preflight is not None:
        return preflight

    location_target = parse_location(args.target)
    initial_file = location_target["path"] if location_target is not None else None
    try:
        with backend_factory(context, initial_file=initial_file) as backend:
            lookup = (lambda query: semantic_symbol_search(context, backend, query)) if getattr(backend, "supports_workspace_symbols", False) or hasattr(backend, "document_symbols") else None
            resolved = resolve_target(args.target, symbol_lookup=lookup)
            if resolved.status != "ok":
                return CommandResult(command="refs", status=resolved.status, results=resolved.results, diagnostics=resolved.diagnostics)
            target = resolved.results[0]
            results = sort_locations(backend.references(target["path"], target["line"], target["column"]))
    except RuntimeError as exc:
        return CommandResult(
            command="refs",
            status="error",
            diagnostics=[{"error_kind": "setup_failure", "message": str(exc), "next_step": "Install clangd or expose it on PATH."}],
        )

    return CommandResult(command="refs", status="ok" if results else "no_results", results=results)
