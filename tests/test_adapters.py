from pathlib import Path

from clangd_probe.adapters import resolve_adapter
from clangd_probe.adapters.base import BaseAdapter


class ConflictingAdapter(BaseAdapter):
    name = "conflict"
    priority = 20
    supports_profiles = False

    def match(self, project_root: Path) -> bool:
        return (project_root / "match.conflict").exists()


def test_generic_adapter_is_fallback(tmp_path):
    selection = resolve_adapter(tmp_path)
    assert selection.status == "ok"
    assert selection.adapter.name == "generic"


def test_sparta_adapter_beats_generic_without_ambiguity(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")

    selection = resolve_adapter(tmp_path)
    assert selection.status == "ok"
    assert selection.adapter.name == "sparta"
    assert selection.conflicts == []


def test_adapter_conflicts_are_reported(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    (tmp_path / "match.conflict").write_text("", encoding="utf-8")

    selection = resolve_adapter(tmp_path, extra_adapters=[ConflictingAdapter()])
    assert selection.status == "ambiguous"
    assert sorted(selection.conflicts) == ["conflict", "sparta"]


def test_profile_passthrough_is_supported_for_sparta(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")

    selection = resolve_adapter(tmp_path, requested_profile="mpi_debug")
    assert selection.status == "ok"
    assert selection.adapter.name == "sparta"
    assert selection.active_profile == "mpi_debug"


def test_profile_request_on_adapter_without_profiles_is_unsupported(tmp_path):
    selection = resolve_adapter(tmp_path, requested_profile="mpi_debug")
    assert selection.status == "unsupported"
    assert selection.adapter.name == "generic"
    assert selection.diagnostics[0]["error_kind"] == "discovery_failure"

