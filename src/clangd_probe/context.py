from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .discovery import DiscoveryResult


@dataclass
class ExecutionContext:
    project_root: str | None = None
    active_compdb: str | None = None
    active_profile: str | None = None
    adapter: str = "generic"
    backend: str = "clangd"
    verbose: bool = False
    limit: int | None = None
    daemon_mode: str = "auto"
    last_results: list[object] = field(default_factory=list)
    inside_daemon: bool = False
    shared_backend: object | None = None
    symbol_cache: dict[str, list[object]] | None = None
    document_symbol_cache: dict[str, list[object]] | None = None

    @classmethod
    def from_namespace(cls, args) -> "ExecutionContext":
        project_root = _resolve_optional_path(getattr(args, "project", None))
        active_compdb = _resolve_optional_path(getattr(args, "compdb", None))
        return cls(
            project_root=project_root,
            active_compdb=active_compdb,
            active_profile=getattr(args, "profile", None),
            verbose=bool(getattr(args, "verbose", False)),
            limit=getattr(args, "limit", None),
            daemon_mode=getattr(args, "daemon_mode", "auto"),
        )

    def apply_discovery(self, discovery: DiscoveryResult) -> None:
        self.project_root = _resolve_path_obj(discovery.project_root)
        self.active_compdb = _resolve_path_obj(discovery.active_compdb)
        self.active_profile = discovery.active_profile
        self.adapter = discovery.adapter
        self.backend = discovery.backend


def _resolve_optional_path(value: str | None) -> str | None:
    if value is None:
        return None
    return str(Path(value).resolve())


def _resolve_path_obj(value: Path | None) -> str | None:
    if value is None:
        return None
    return str(value.resolve())
