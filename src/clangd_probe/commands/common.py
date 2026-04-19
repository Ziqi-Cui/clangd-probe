from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from ..discovery import discover
from ..lsp_client import LspClient
from ..output import CommandResult
from ..resolve import match_score


def prepare_semantic_context(command: str, args, context):
    discovery = discover(
        project=getattr(args, "project", None),
        compdb=getattr(args, "compdb", None),
        profile=getattr(args, "profile", None),
    )
    context.apply_discovery(discovery)
    if getattr(context, "inside_daemon", False):
        context.backend = "clangd-daemon"
    if discovery.status == "ok":
        return None

    status = discovery.status if discovery.status in {"ambiguous", "unsupported"} else "error"
    return CommandResult(
        command=command,
        status=status,
        warnings=discovery.warnings,
        diagnostics=with_next_step(
            discovery.diagnostics,
            "Provide --compdb explicitly or resolve project discovery before running semantic commands.",
        ),
    )


def with_next_step(diagnostics, next_step):
    updated = []
    for diagnostic in diagnostics:
        item = dict(diagnostic)
        item.setdefault("next_step", next_step)
        updated.append(item)
    return updated


@contextmanager
def backend_factory(context, initial_file=None):
    shared_backend = getattr(context, "shared_backend", None)
    if shared_backend is not None:
        yield shared_backend
        return

    clangd_path = shutil.which("clangd")
    if clangd_path is None:
        raise RuntimeError("clangd is not available on PATH")

    command = [clangd_path]
    if context.active_compdb:
        command.append(f"--compile-commands-dir={Path(context.active_compdb).parent}")

    with LspClient(command) as client:
        client.initialize(context.project_root or Path.cwd(), initial_file=initial_file)
        yield client


def sort_locations(rows):
    return sorted(rows, key=lambda row: (row.get("path", ""), row.get("line", 0), row.get("column", 0)))


def sort_symbols(rows):
    return sorted(
        rows,
        key=lambda row: (
            row.get("qualified_name") or row.get("name") or "",
            row.get("path") or "",
            row.get("line", 0),
            row.get("column", 0),
        ),
    )


def rank_symbols_for_query(query, rows):
    ranked = []
    for row in rows:
        score = match_score(query, row)
        if score <= 0:
            continue
        ranked.append((score, row))
    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].get("qualified_name") or item[1].get("name") or "",
            item[1].get("path") or "",
            item[1].get("line", 0),
            item[1].get("column", 0),
        )
    )
    return [row for _, row in ranked]


def semantic_symbol_search(context, backend, query):
    cache = getattr(context, "symbol_cache", None)
    if cache is not None and query in cache:
        return list(cache[query])

    results = []
    if getattr(backend, "supports_workspace_symbols", False):
        results = list(backend.workspace_symbols(query))
        if results:
            if cache is not None:
                cache[query] = list(results)
            return results

    if not can_fallback_to_document_symbols(context, backend):
        return results

    fallback = []
    for path in candidate_project_source_files(context, query):
        rows = cached_document_symbols(context, backend, str(path))
        for row in rows or []:
            if match_score(query, row) > 0:
                fallback.append(refine_symbol_row(row))
    if cache is not None:
        cache[query] = list(fallback)
    return fallback


def can_fallback_to_document_symbols(context, backend):
    return bool(getattr(context, "active_compdb", None)) and hasattr(backend, "document_symbols")


def project_source_files(context):
    compdb_path = getattr(context, "active_compdb", None)
    if not compdb_path:
        return []

    try:
        payload = json.loads(Path(compdb_path).read_text(encoding="utf-8"))
    except Exception:
        return []

    paths = []
    seen = set()
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        file_value = entry.get("file")
        if not file_value:
            continue
        file_path = Path(file_value)
        if not file_path.is_absolute():
            base = Path(entry.get("directory") or Path(compdb_path).parent)
            file_path = base / file_path
        resolved = file_path.resolve()
        if resolved.suffix not in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"}:
            continue
        if not resolved.exists():
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        paths.append(resolved)
    return paths


def candidate_project_source_files(context, query):
    files = project_source_files(context)
    if not files:
        return []

    query_text = query.lower()
    tokens = query_tokens(query_text)
    scored = []
    for path in files:
        score = source_path_score(path, query_text, tokens)
        if score <= 0:
            continue
        scored.append((score, path))

    if not scored:
        return files[:20]

    scored.sort(key=lambda item: (-item[0], str(item[1])))
    return [path for _, path in scored[:20]]


def query_tokens(query):
    pieces = [piece for piece in query.replace("::", " ").replace("_", " ").split() if piece]
    tokens = []
    for piece in pieces:
        cleaned = "".join(ch for ch in piece if ch.isalnum())
        if cleaned:
            tokens.append(cleaned)
    return tokens


def source_path_score(path, query_text, tokens):
    lowered_name = path.name.lower()
    lowered_stem = path.stem.lower()
    score = 0

    if query_text and query_text in lowered_name:
        score += 10
    if query_text and query_text in lowered_stem:
        score += 8

    for token in tokens:
        if token in lowered_stem:
            score += 6
        elif token in lowered_name:
            score += 4

    if score < 8 and tokens:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            return score
        if query_text and query_text in content:
            score += 6
        for token in tokens:
            if token in content:
                score += 2

    return score


def refine_symbol_row(row):
    path = row.get("path")
    line = int(row.get("line", 0) or 0)
    if not path or line <= 0:
        return row

    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()[line - 1]
    except Exception:
        return row

    candidates = []
    for value in (row.get("qualified_name"), row.get("name")):
        text_value = str(value or "")
        if not text_value:
            continue
        if "::" in text_value:
            candidates.append(text_value.split("::")[-1])
        candidates.append(text_value)

    for candidate in candidates:
        column = text.find(candidate)
        if column != -1:
            refined = dict(row)
            refined["column"] = column + 1
            return refined

    return row


def cached_document_symbols(context, backend, path):
    cache = getattr(context, "document_symbol_cache", None)
    if cache is not None and path in cache:
        return list(cache[path])
    try:
        rows = backend.document_symbols(path)
    except Exception:
        rows = []
    if cache is not None:
        cache[path] = list(rows)
    return rows
