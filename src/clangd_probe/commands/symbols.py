from __future__ import annotations

from ..output import CommandResult
from .common import backend_factory, prepare_semantic_context, sort_symbols


def run(args, context):
    preflight = prepare_semantic_context("symbols", args, context)
    if preflight is not None:
        return preflight

    try:
        with backend_factory(context, initial_file=args.path) as backend:
            results = sort_symbols(backend.document_symbols(args.path))
    except RuntimeError as exc:
        return CommandResult(
            command="symbols",
            status="error",
            diagnostics=[{"error_kind": "setup_failure", "message": str(exc), "next_step": "Install clangd or expose it on PATH."}],
        )

    if not results:
        return CommandResult(command="symbols", status="no_results", results=[])

    truncated = False
    if context.limit is not None and len(results) > context.limit:
        results = results[:context.limit]
        truncated = True

    return CommandResult(command="symbols", status="ok", results=results, truncated=truncated)
