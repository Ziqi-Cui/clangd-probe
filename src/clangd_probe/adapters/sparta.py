from __future__ import annotations

from pathlib import Path

from .base import BaseAdapter


class SpartaAdapter(BaseAdapter):
    name = "sparta"
    priority = 10
    supports_profiles = True

    def match(self, project_root: Path) -> bool:
        has_src = (project_root / "src").is_dir()
        has_repo_markers = (project_root / "AGENTS.md").exists() or (
            project_root / "BUILD_CMAKE.md"
        ).exists()
        return has_src and has_repo_markers

    def profile_names(self, project_root: Path) -> list[str]:
        return ["serial_debug", "mpi_debug", "kokkos_omp"]

    def candidate_paths(self, project_root: Path) -> list[Path]:
        candidates = [project_root / "build-clangd" / "compile_commands.json"]
        candidates.append(project_root / "compile_commands.json")
        candidates.append(project_root / "build" / "compile_commands.json")
        candidates.extend(
            child / "compile_commands.json" for child in sorted(project_root.glob("cmake-build-*"))
        )
        return candidates

    def profile_to_candidates(self, project_root: Path, profile: str) -> list[Path]:
        return [project_root / "build-clangd" / "compile_commands.json"] + self.candidate_paths(project_root)

    def diagnostic_hints(self, project_root: Path) -> list[str]:
        return [
            "Prefer build-clangd/ when available.",
            "If no compilation database exists yet, run tools/dev/setup_clangd.sh <serial_debug|mpi_debug|kokkos_omp>.",
            "Use mpi_debug when mpi.h must resolve instead of STUBS.",
            "Use kokkos_omp before touching KOKKOS-backed translation units.",
        ]
