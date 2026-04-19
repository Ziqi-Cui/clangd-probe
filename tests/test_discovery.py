from pathlib import Path

from clangd_probe.adapters.base import BaseAdapter
from clangd_probe.discovery import discover


class ConflictingAdapter(BaseAdapter):
    name = "conflict"
    priority = 20
    supports_profiles = False

    def match(self, project_root: Path) -> bool:
        return (project_root / "match.conflict").exists()


def write_compdb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    return path


def test_explicit_project_and_compdb_win(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    compdb = write_compdb(root / "build-custom" / "compile_commands.json")

    result = discover(project=root, compdb=compdb)

    assert result.status == "ok"
    assert result.project_root == root.resolve()
    assert result.active_compdb == compdb.resolve()


def test_upward_search_finds_compile_commands(tmp_path):
    root = tmp_path / "repo"
    nested = root / "src" / "subdir"
    nested.mkdir(parents=True)
    compdb = write_compdb(root / "compile_commands.json")

    result = discover(cwd=nested)

    assert result.status == "ok"
    assert result.project_root == root.resolve()
    assert result.active_compdb == compdb.resolve()


def test_sparta_profile_prefers_build_clangd(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    direct = write_compdb(root / "build-clangd" / "compile_commands.json")
    write_compdb(root / "build" / "compile_commands.json")

    result = discover(project=root, profile="mpi_debug")

    assert result.status == "ok"
    assert result.adapter == "sparta"
    assert result.active_profile == "mpi_debug"
    assert result.active_compdb == direct.resolve()


def test_multiple_candidates_are_ambiguous(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "build" / "compile_commands.json")
    write_compdb(root / "cmake-build-debug" / "compile_commands.json")

    result = discover(project=root)

    assert result.status == "ambiguous"
    assert result.active_compdb is None
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"


def test_project_compdb_mismatch_emits_warning(tmp_path):
    project_root = tmp_path / "project"
    foreign_root = tmp_path / "foreign"
    project_root.mkdir()
    foreign_root.mkdir()
    compdb = write_compdb(foreign_root / "compile_commands.json")

    result = discover(project=project_root, compdb=compdb)

    assert result.status == "ok"
    assert result.project_root == project_root.resolve()
    assert result.active_compdb == compdb.resolve()
    assert result.warnings


def test_profile_without_support_is_unsupported(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    result = discover(project=root, profile="mpi_debug")

    assert result.status == "unsupported"
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"


def test_unknown_profile_is_discovery_failure(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    write_compdb(root / "build-clangd" / "compile_commands.json")

    result = discover(project=root, profile="wrong_profile")

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"
    assert any("setup_clangd.sh" in item["message"] for item in result.diagnostics[1:])


def test_sparta_missing_compdb_includes_setup_hint(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")

    result = discover(project=root)

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"
    assert any("setup_clangd.sh" in item["message"] for item in result.diagnostics[1:])


def test_adapter_conflict_bubbles_into_discovery(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    (root / "match.conflict").write_text("", encoding="utf-8")
    write_compdb(root / "build-clangd" / "compile_commands.json")

    result = discover(project=root, extra_adapters=[ConflictingAdapter()])

    assert result.status == "ambiguous"
    assert sorted(result.conflicts) == ["conflict", "sparta"]
