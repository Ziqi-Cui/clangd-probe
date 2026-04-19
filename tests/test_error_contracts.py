from __future__ import annotations

from argparse import Namespace
import importlib
from pathlib import Path

from clangd_probe.commands import check as check_command
from clangd_probe.adapters.base import BaseAdapter
from clangd_probe.context import ExecutionContext
from clangd_probe.discovery import discover


def make_args(**overrides):
    base = {
        "project": None,
        "compdb": None,
        "profile": None,
        "verbose": False,
        "limit": None,
        "json_output": False,
        "target": None,
        "query": None,
        "path": None,
    }
    base.update(overrides)
    return Namespace(**base)


def write_compdb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    return path


class ConflictingAdapter(BaseAdapter):
    name = "conflict"
    priority = 20
    supports_profiles = False

    def match(self, project_root: Path) -> bool:
        return (project_root / "match.conflict").exists()


def test_discovery_unclear_root_reports_failure(tmp_path):
    result = discover(cwd=tmp_path)
    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"


def test_discovery_adapter_conflict_reports_ambiguity(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    (root / "match.conflict").write_text("", encoding="utf-8")
    write_compdb(root / "build-clangd" / "compile_commands.json")

    result = discover(project=root, extra_adapters=[ConflictingAdapter()])
    assert result.status == "ambiguous"


def test_check_missing_clangd_is_setup_failure(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: None)

    args = make_args(project=str(root), path=str(source))
    result = check_command.run(args, ExecutionContext.from_namespace(args))
    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "setup_failure"


def test_check_missing_compdb_is_discovery_failure(tmp_path):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main() { return 0; }\n", encoding="utf-8")

    args = make_args(project=str(root), path=str(source))
    result = check_command.run(args, ExecutionContext.from_namespace(args))
    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"


def test_semantic_no_results_contract(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.find")

    class Backend:
        supports_workspace_symbols = True
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        def workspace_symbols(self, query): return []

    monkeypatch.setattr(mod, "backend_factory", lambda context, initial_file=None: Backend())

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")
    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), query="Missing")
    result = mod.run(args, ExecutionContext.from_namespace(args))
    assert result.status == "no_results"


def test_semantic_ambiguous_contract(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.def")

    class Backend:
        supports_workspace_symbols = True
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        def workspace_symbols(self, query):
            return [
                {"name": "solve", "qualified_name": "A::solve", "path": "/tmp/a.cpp", "line": 1, "column": 1},
                {"name": "solve", "qualified_name": "B::solve", "path": "/tmp/b.cpp", "line": 1, "column": 1},
            ]

    monkeypatch.setattr(mod, "backend_factory", lambda context, initial_file=None: Backend())

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")
    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target="solve")
    result = mod.run(args, ExecutionContext.from_namespace(args))
    assert result.status == "ambiguous"


def test_semantic_unsupported_contract(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.find")

    class Backend:
        supports_workspace_symbols = False
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False

    monkeypatch.setattr(mod, "backend_factory", lambda context, initial_file=None: Backend())

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")
    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), query="alpha")
    result = mod.run(args, ExecutionContext.from_namespace(args))
    assert result.status == "unsupported"


def test_parse_failure_contract(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main( { return 0; }\n", encoding="utf-8")
    compdb = write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: "/usr/bin/clangd")
    monkeypatch.setattr(
        check_command,
        "run_clangd",
        lambda argv: check_command.CompletedCheck(returncode=1, stdout="E[00:00:00.001] parse failure\n", stderr=""),
    )

    args = make_args(project=str(root), compdb=str(compdb), path=str(source))
    result = check_command.run(args, ExecutionContext.from_namespace(args))
    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "parse_failure"
