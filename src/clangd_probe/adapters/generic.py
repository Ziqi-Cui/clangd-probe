from __future__ import annotations

from pathlib import Path

from .base import BaseAdapter


class GenericAdapter(BaseAdapter):
    name = "generic"
    priority = 0
    supports_profiles = False

    def match(self, project_root: Path) -> bool:
        return True

    def candidate_paths(self, project_root: Path) -> list[Path]:
        candidates = [project_root / "compile_commands.json"]
        candidates.append(project_root / "build-clangd" / "compile_commands.json")
        candidates.append(project_root / "build" / "compile_commands.json")
        candidates.extend(
            child / "compile_commands.json" for child in sorted(project_root.glob("cmake-build-*"))
        )
        return candidates
