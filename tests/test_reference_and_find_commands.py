from __future__ import annotations

from argparse import Namespace
import importlib
import json
from pathlib import Path

from clangd_probe.commands.common import refine_symbol_row
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
        "query": None,
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

    def references(self, path, line, column):
        return [
            {"path": str(Path(path).resolve()), "line": 12, "column": 1},
            {"path": str(Path(path).resolve()), "line": 6, "column": 3},
        ]

    def workspace_symbols(self, query):
        if query == "Missing":
            return []
        return [
            {"name": "zeta", "qualified_name": "zeta", "path": "/tmp/z.cpp", "line": 10, "column": 1, "kind": 12},
            {"name": "alpha", "qualified_name": "alpha", "path": "/tmp/a.cpp", "line": 3, "column": 2, "kind": 12},
            {"name": "beta", "qualified_name": "beta", "path": "/tmp/b.cpp", "line": 5, "column": 4, "kind": 12},
        ]


def backend_factory(_context, initial_file=None):
    return FakeBackend()


def test_refs_from_location(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.refs")
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
    assert result.results[0]["line"] == 6


def test_refs_from_symbol(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.refs")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target="alpha")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["line"] == 6


def test_refs_from_qualified_symbol_does_not_open_fake_initial_file(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.refs")
    seen = {}

    class QualifiedBackend(FakeBackend):
        def workspace_symbols(self, query):
            return [
                {
                    "name": "next",
                    "qualified_name": "Variable::next",
                    "path": "/tmp/variable.cpp",
                    "line": 12,
                    "column": 3,
                    "kind": 12,
                }
            ]

    def qualified_backend_factory(_context, initial_file=None):
        seen["initial_file"] = initial_file
        return QualifiedBackend()

    monkeypatch.setattr(mod, "backend_factory", qualified_backend_factory)

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), target="Variable::next")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert seen["initial_file"] is None


def test_find_query_supports_limit_and_truncated(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.find")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), query="a", limit=2)
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert len(result.results) == 2
    assert result.truncated is True
    assert result.results[0]["name"] == "alpha"


def test_find_no_results_is_distinct(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.find")
    monkeypatch.setattr(mod, "backend_factory", backend_factory)

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), query="Missing")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "no_results"


def test_find_unsupported_without_search_surface(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.find")

    class NoSearchBackend(FakeBackend):
        supports_workspace_symbols = False

    monkeypatch.setattr(mod, "backend_factory", lambda _context, initial_file=None: NoSearchBackend())

    root = tmp_path / "repo"
    root.mkdir()
    write_compdb(root / "compile_commands.json")

    args = make_args(project=str(root), compdb=str(root / "compile_commands.json"), query="alpha")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "unsupported"


def test_find_falls_back_to_document_symbols_when_workspace_search_is_empty(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.find")

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

    monkeypatch.setattr(mod, "backend_factory", lambda _context, initial_file=None: FallbackBackend())

    root = tmp_path / "repo"
    root.mkdir()
    source = root / "variable.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    compdb = write_compdb_entries(root / "compile_commands.json", source)

    args = make_args(project=str(root), compdb=str(compdb), query="Variable")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["qualified_name"] == "Variable::next"


def test_refs_fall_back_to_document_symbols_when_workspace_search_is_empty(tmp_path, monkeypatch):
    mod = importlib.import_module("clangd_probe.commands.refs")

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

    monkeypatch.setattr(mod, "backend_factory", lambda _context, initial_file=None: FallbackBackend())

    root = tmp_path / "repo"
    root.mkdir()
    source = root / "variable.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    compdb = write_compdb_entries(root / "compile_commands.json", source)

    args = make_args(project=str(root), compdb=str(compdb), target="Variable::next")
    context = ExecutionContext.from_namespace(args)
    result = mod.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["path"] == str(source.resolve())


def test_refine_symbol_row_moves_column_to_symbol_token(tmp_path):
    source = tmp_path / "variable.cpp"
    source.write_text("int Variable::next(int narg, char **arg)\n", encoding="utf-8")

    row = {
        "name": "Variable::next",
        "qualified_name": "",
        "path": str(source.resolve()),
        "line": 1,
        "column": 1,
        "kind": 12,
    }

    refined = refine_symbol_row(row)

    assert refined["column"] == 15
