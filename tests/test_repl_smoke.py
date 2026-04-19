from __future__ import annotations

from argparse import Namespace

from clangd_probe.context import ExecutionContext
from clangd_probe.output import CommandResult
from clangd_probe.repl import run_session


def make_context():
    return ExecutionContext(project_root="/tmp/repo", active_compdb="/tmp/repo/compile_commands.json")


def dispatch_factory(calls):
    def dispatch(argv, context):
        command = argv[0]
        calls.append((command, tuple(argv[1:]), context.project_root, list(context.last_results)))
        if command == "env":
            return CommandResult(command="env", status="ok", results=[{"path": "/tmp/repo/demo.cpp", "line": 1, "column": 1}])
        if command == "def":
            return CommandResult(command="def", status="ok", results=[{"path": "/tmp/repo/demo.cpp", "line": 4, "column": 2}])
        if command == "hover":
            return CommandResult(command="hover", status="ok", results=[{"value": "hover"}])
        if command == "refs":
            return CommandResult(command="refs", status="ok", results=[{"path": "/tmp/repo/demo.cpp", "line": 7, "column": 3}])
        if command == "symbols":
            return CommandResult(command="symbols", status="ok", results=[{"name": "Demo"}])
        if command == "find":
            return CommandResult(command="find", status="ok", results=[{"name": "Demo::solve"}])
        if command == "check":
            return CommandResult(command="check", status="ok", results=[{"parse_usable": True}])
        return CommandResult(command=command, status="error")

    return dispatch


def test_repl_runs_supported_commands_and_reuses_context():
    calls = []
    transcript = run_session(
        [
            "env",
            "def /tmp/repo/demo.cpp:4:2",
            "hover @last",
            "refs @last",
            "symbols /tmp/repo/demo.cpp",
            "find Demo::solve",
            "check /tmp/repo/demo.cpp",
            "quit",
        ],
        make_context(),
        dispatch_factory(calls),
    )

    assert [item["command"] for item in transcript] == ["env", "def", "hover", "refs", "symbols", "find", "check"]
    assert calls[2][1] == ("/tmp/repo/demo.cpp:4:2",)
    assert all(item["status"] == "ok" for item in transcript)


def test_repl_starts_cleanly_and_exit_is_stable():
    transcript = run_session(["exit"], make_context(), dispatch_factory([]))
    assert transcript == []

