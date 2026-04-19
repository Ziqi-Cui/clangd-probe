from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from clangd_probe.commands import check as check_command
from clangd_probe.commands import env as env_command
from clangd_probe.context import ExecutionContext


def make_args(**overrides):
    base = {
        "project": None,
        "compdb": None,
        "profile": None,
        "verbose": False,
        "limit": None,
        "json_output": False,
        "path": None,
    }
    base.update(overrides)
    return Namespace(**base)


def write_compdb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    return path


def test_env_reports_discovered_context_and_clangd_availability(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    write_compdb(root / "build-clangd" / "compile_commands.json")

    monkeypatch.setattr(env_command, "find_clangd", lambda: "/usr/bin/clangd")

    args = make_args(project=str(root), profile="serial_debug", verbose=True, limit=5)
    context = ExecutionContext.from_namespace(args)
    result = env_command.run(args, context)

    assert result.status == "ok"
    assert context.adapter == "sparta"
    assert context.active_profile == "serial_debug"
    assert result.results[0]["clangd_available"] is True
    assert result.results[0]["clangd_path"] == "/usr/bin/clangd"


def test_check_maps_mocked_clangd_success(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "src" / "demo.cpp"
    source.parent.mkdir(parents=True)
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    compdb = write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: "/usr/bin/clangd")

    def fake_run(argv):
        assert argv[0] == "/usr/bin/clangd"
        assert "--check=" + str(source.resolve()) in argv
        assert "--compile-commands-dir=" + str(compdb.parent.resolve()) in argv
        return check_command.CompletedCheck(
            returncode=0,
            stdout="I[00:00:00.000] Loading compilation database...\nI[00:00:00.001] Building AST...\n",
            stderr="",
        )

    monkeypatch.setattr(check_command, "run_clangd", fake_run)

    args = make_args(project=str(root), compdb=str(compdb), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = check_command.run(args, context)

    assert result.status == "ok"
    assert result.results[0]["parse_usable"] is True
    assert result.results[0]["clangd_path"] == "/usr/bin/clangd"


def test_check_handles_missing_clangd(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: None)

    args = make_args(project=str(root), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = check_command.run(args, context)

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "setup_failure"
    assert "next_step" in result.diagnostics[0]


def test_check_handles_missing_compdb(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main() { return 0; }\n", encoding="utf-8")

    monkeypatch.setattr(check_command, "find_clangd", lambda: "/usr/bin/clangd")

    args = make_args(project=str(root), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = check_command.run(args, context)

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "discovery_failure"
    assert "next_step" in result.diagnostics[0]


def test_check_summarizes_parse_failure(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main( { return 0; }\n", encoding="utf-8")
    compdb = write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: "/usr/bin/clangd")
    monkeypatch.setattr(
        check_command,
        "run_clangd",
        lambda _argv: check_command.CompletedCheck(
            returncode=1,
            stdout="E[00:00:00.001] expected ')'\n",
            stderr="",
        ),
    )

    args = make_args(project=str(root), compdb=str(compdb), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = check_command.run(args, context)

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "parse_failure"
    assert result.results[0]["parse_usable"] is False
    assert "next_step" in result.diagnostics[0]


def test_check_prefers_actual_error_line_in_summary(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    compdb = write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: "/usr/bin/clangd")
    monkeypatch.setattr(
        check_command,
        "run_clangd",
        lambda _argv: check_command.CompletedCheck(
            returncode=1,
            stdout="I[00:00:00.000] Ubuntu clangd version 14\nE[00:00:00.100] no such file or directory\n",
            stderr="",
        ),
    )

    args = make_args(project=str(root), compdb=str(compdb), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = check_command.run(args, context)

    assert result.status == "error"
    assert "no such file or directory" in result.diagnostics[0]["message"]


def test_check_explains_standard_mismatch_parse_failure(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    source = root / "demo.cpp"
    root.mkdir()
    source.write_text("int main() { return 0; }\n", encoding="utf-8")
    compdb = write_compdb(root / "compile_commands.json")

    monkeypatch.setattr(check_command, "find_clangd", lambda: "/usr/bin/clangd")
    monkeypatch.setattr(
        check_command,
        "run_clangd",
        lambda _argv: check_command.CompletedCheck(
            returncode=1,
            stdout="E[00:00:00.001] C++ versions less than C++17 are not supported.\n",
            stderr="",
        ),
    )

    args = make_args(project=str(root), compdb=str(compdb), path=str(source))
    context = ExecutionContext.from_namespace(args)
    result = check_command.run(args, context)

    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "parse_failure"
    assert "-std=" in result.diagnostics[0]["next_step"]
    assert "C++ standard" in result.diagnostics[0]["next_step"]
