from __future__ import annotations

from ..output import CommandResult
from .common import backend_factory, can_fallback_to_document_symbols, prepare_semantic_context, rank_symbols_for_query, semantic_symbol_search


def run(args, context):
    preflight = prepare_semantic_context("find", args, context)
    if preflight is not None:
        return preflight

    try:
        with backend_factory(context) as backend:
            if not getattr(backend, "supports_workspace_symbols", False) and not can_fallback_to_document_symbols(context, backend):
                return CommandResult(
                    command="find",
                    status="unsupported",
                    diagnostics=[{"error_kind": "setup_failure", "message": "workspace symbol search is unavailable in the active backend"}],
                )
            results = rank_symbols_for_query(args.query, semantic_symbol_search(context, backend, args.query))
    except RuntimeError as exc:
        return CommandResult(
            command="find",
            status="error",
            diagnostics=[{"error_kind": "setup_failure", "message": str(exc), "next_step": "Install clangd or expose it on PATH."}],
        )

    if not results:
        return CommandResult(command="find", status="no_results", results=[])

    truncated = False
    if context.limit is not None and len(results) > context.limit:
        results = results[:context.limit]
        truncated = True

    return CommandResult(command="find", status="ok", results=results, truncated=truncated)
