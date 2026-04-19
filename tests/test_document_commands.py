from __future__ import annotations

from argparse import Namespace
import importlib
import json
from pathlib import Path

from clangd_probe.context import ExecutionContext


def make_args(**overrides):
    base = {
        "project": None,
        "compdb": None,
        "profile": None,
        "verbose": False,
        "limit": None,
        "json_output": False,
        "target": None,
        "path": None,
    }
    base.update(overrides)
    return Namespace(**base)


def write_compdb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    return path


def write_compdb_entries(path: Path, *files: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for file_path in files:
        entries.append(
            {
                "directory": str(file_path.parent.resolve()),
                "file": str(file_path.resolve()),
                "command": f"c++ -c {file_path.name}",
            }
        )
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


class FakeBackend:
    supports_workspace_symbols = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def definition(self, path, line, column):
        return [
            {"path": str(Path(path).resolve()), "line": line + 1, "column": column + 1},
            {"path": str(Path(path).resolve()), "line": line, "column": column},
        ]

    def hover(self, path, line, column):
        return {"kind": "markdown", "value": f"hover:{Path(path).name}:{line}:{column}"}

    def document_symbols(self, path):
        return [
            {
                "name": "Beta",
                "qualified_name": "Beta",
                "path": str(Path(path).resolve()),
                "line": 9,
                "column": 2,
                "kind": 5,
            },
            {
                "name": "Alpha",
                "qualified_name": "Alpha",
                "path": str(Path(path).resolve()),
                "line": 3,
                "column": 1,
                "kind": 5,
            },
        ]

    def workspace_symbols(self, query):
        if query == "Missing":
            return []
        return [
            {
                "name": "solve_extra",
                "qualified_name": "CollideBGK::solve_extra",
                "path": "/tmp/extra.cpp",
                "line": 8,
                "column": 2,
                "kind": 12,
            },
            {
                "name": "solve",
                "qualified_name": "CollideBGK::solve",
                "path": "/tmp/demo.cpp",
                "line": 4,
                "column": 3,
                "kind": 12,
            },
        ]


def backend_factory(_context, initial_file=None):
    return FakeBackend()


def test_def_from_location(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.def")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target=f"{source}:4:3")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["line"] == 4
    assert result.results[1]["line"] == 5


def test_def_from_symbol(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.def")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target="CollideBGK::solve")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["path"] == "/tmp/demo.cpp"


def test_hover_command(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.hover")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target=f"{source}:2:1")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert "hover:demo.cpp:2:1" in result.results[0]["value"]


def test_hover_no_result_is_distinct(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.hover")

    class NoHoverBackend(FakeBackend):
        def hover(self, path, line, column):
            return None

    monkeypatch.setattr(mod, "backend_factory", lambda _context, initial_file=None: NoHoverBackend())

    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target=f"{source}:2:1")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "no_results"
    assert result.results == []


def test_symbols_command_sorts_results(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.symbols")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["name"] == "Alpha"


def test_symbols_command_applies_limit_and_truncated(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.symbols")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), path=str(source), limit=1)
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert len(result.results) == 1
    assert result.truncated is True


def test_symbol_form_is_unsupported_without_semantic_search(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.def")

    class NoSearchBackend:
        supports_workspace_symbols = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod, "backend_factory", lambda _context, initial_file=None: NoSearchBackend())

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target="CollideBGK::solve")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "unsupported"


def test_def_missing_location_file_is_structured_error(tmp_path):
    mod = importlib.import_module("clangd_probe.commands.def")

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    missing = root / "missing.cpp"
    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target=f"{missing}:4:3")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "setup_failure"


def test_def_falls_back_to_document_symbols_when_workspace_search_is_empty(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.def")

    class FallbackBackend(FakeBackend):
        def workspace_symbols(self, query):
            return []

        def document_symbols(self, path):
            if path.endswith("variable.cpp"):
                return [
                    {
                        "name": "next",
                        "qualified_name": "Variable::next",
                        "path": path,
                        "line": 12,
                        "column": 3,
                        "kind": 12,
                    }
                ]
            return []

    root = tmp_path / "repo"
    source = root / "variable.cpp"
    root.mkdir()
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    compdb = write_compdb_entries(root / "compile_commands.json", source)

    monkeypatch.setattr(mod, "backend_factory", lambda _context, initial_file=None: FallbackBackend())

    args = make_args(project=str(root), compdb=str(compdb), target="Variable::next")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["path"] == str(source.resolve())
