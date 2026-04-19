from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class BaseAdapter:
    name = "base"
    priority = 0
    supports_profiles = False

    def match(self, project_root: Path) -> bool:
        return False

    def candidate_paths(self, project_root: Path) -> list[Path]:
        return []

    def profile_names(self, project_root: Path) -> list[str]:
        return []

    def profile_to_candidates(self, project_root: Path, profile: str) -> list[Path]:
        return []

    def diagnostic_hints(self, project_root: Path) -> list[str]:
        return []


@dataclass
class AdapterSelection:
    status: str
    adapter: BaseAdapter
    active_profile: str | None = None
    diagnostics: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
