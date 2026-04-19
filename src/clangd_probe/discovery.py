from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .adapters import resolve_adapter


@dataclass
class DiscoveryResult:
    status: str
    project_root: Path | None = None
    active_compdb: Path | None = None
    active_profile: str | None = None
    adapter: str = "generic"
    backend: str = "clangd"
    warnings: list[dict[str, str]] = field(default_factory=list)
    diagnostics: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def discover(
    project: str | Path | None = None,
    compdb: str | Path | None = None,
    profile: str | None = None,
    cwd: str | Path | None = None,
    extra_adapters=None,
) -> DiscoveryResult:
    cwd_path = Path.cwd() if cwd is None else Path(cwd).resolve()
    explicit_project = Path(project).resolve() if project is not None else None
    explicit_compdb = Path(compdb).resolve() if compdb is not None else None

    if explicit_project is not None:
        root = explicit_project
    elif explicit_compdb is not None:
        root = explicit_compdb.parent
    else:
        root, upward_candidates = discover_from_upward_search(cwd_path)
        if root is None:
            return DiscoveryResult(
                status="error",
                project_root=cwd_path,
                active_profile=profile,
                diagnostics=[diag("discovery_failure", "could not discover a project root or compilation database")],
            )
        if upward_candidates is not None:
            return finalize_discovery(root, upward_candidates, profile, extra_adapters)

    warnings = []
    if explicit_compdb is not None and explicit_project is not None:
        try:
            explicit_compdb.relative_to(explicit_project)
        except ValueError:
            warnings.append(
                {
                    "warning_kind": "discovery_mismatch",
                    "message": "explicit --compdb is outside the explicit --project root",
                }
            )

    if explicit_compdb is not None:
        return finalize_discovery(root, [explicit_compdb], profile, extra_adapters, warnings)

    adapter_selection = resolve_adapter(root, requested_profile=profile, extra_adapters=extra_adapters)
    if adapter_selection.status in {"ambiguous", "unsupported"}:
        return DiscoveryResult(
            status=adapter_selection.status,
            project_root=root,
            active_profile=profile,
            adapter=adapter_selection.adapter.name,
            diagnostics=adapter_selection.diagnostics,
            conflicts=adapter_selection.conflicts,
            warnings=warnings,
        )

    adapter = adapter_selection.adapter
    if profile:
        known_profiles = adapter.profile_names(root)
        if profile not in known_profiles:
            return DiscoveryResult(
                status="error",
                project_root=root,
                active_profile=profile,
                adapter=adapter.name,
                diagnostics=diag_list(
                    "discovery_failure",
                    f"unknown profile {profile!r} for adapter {adapter.name}",
                    adapter.diagnostic_hints(root),
                ),
                warnings=warnings,
            )
        ordered = existing_paths(adapter.profile_to_candidates(root, profile))
        if ordered:
            return DiscoveryResult(
                status="ok",
                project_root=root,
                active_compdb=ordered[0],
                active_profile=profile,
                adapter=adapter.name,
                warnings=warnings,
            )

    candidates = existing_paths(adapter.candidate_paths(root))
    return finalize_discovery(root, candidates, profile, extra_adapters, warnings)


def finalize_discovery(root, candidates, profile, extra_adapters=None, warnings=None):
    warnings = [] if warnings is None else list(warnings)
    adapter_selection = resolve_adapter(root, requested_profile=profile, extra_adapters=extra_adapters)
    if adapter_selection.status in {"ambiguous", "unsupported"}:
        return DiscoveryResult(
            status=adapter_selection.status,
            project_root=root,
            active_profile=profile,
            adapter=adapter_selection.adapter.name,
            diagnostics=adapter_selection.diagnostics,
            conflicts=adapter_selection.conflicts,
            warnings=warnings,
        )

    adapter = adapter_selection.adapter
    unique_candidates = existing_paths(candidates)
    if not unique_candidates:
        return DiscoveryResult(
            status="error",
            project_root=root,
            active_profile=profile,
            adapter=adapter.name,
            diagnostics=diag_list(
                "discovery_failure",
                "no compile_commands.json candidates found",
                adapter.diagnostic_hints(root),
            ),
            warnings=warnings,
        )
    if len(unique_candidates) > 1:
        return DiscoveryResult(
            status="ambiguous",
            project_root=root,
            active_profile=profile,
            adapter=adapter.name,
            diagnostics=[diag("discovery_failure", "multiple compile_commands.json candidates are equally plausible")],
            warnings=warnings,
        )
    return DiscoveryResult(
        status="ok",
        project_root=root,
        active_compdb=unique_candidates[0],
        active_profile=profile,
        adapter=adapter.name,
        warnings=warnings,
    )


def discover_from_upward_search(start: Path):
    current = start
    while True:
        direct = existing_paths([current / "compile_commands.json"])
        if direct:
            return current, direct

        guessed = generic_candidate_paths(current)
        if guessed:
            return current, guessed

        if current.parent == current:
            return None, None
        current = current.parent


def existing_paths(paths):
    seen = []
    for path in paths:
        resolved = Path(path).resolve()
        if resolved.exists() and resolved not in seen:
            seen.append(resolved)
    return seen


def generic_candidate_paths(root: Path):
    candidates = []
    for candidate in (root / "build-clangd" / "compile_commands.json", root / "build" / "compile_commands.json"):
        if candidate.exists():
            candidates.append(candidate.resolve())
    for child in sorted(root.glob("cmake-build-*")):
        candidate = child / "compile_commands.json"
        if candidate.exists():
            candidates.append(candidate.resolve())
    return candidates


def diag(error_kind: str, message: str) -> dict[str, str]:
    return {"error_kind": error_kind, "message": message}


def diag_list(error_kind: str, message: str, hints: list[str]):
    items = [diag(error_kind, message)]
    for hint in hints:
        items.append({"error_kind": error_kind, "message": hint})
    return items
