from __future__ import annotations

import pytest
from argparse import Namespace

from clangd_probe.cli import build_parser
from clangd_probe.commands import daemon as daemon_command
from clangd_probe.context import ExecutionContext


def parse_args(*argv):
    parser = build_parser()
    return parser.parse_args(list(argv))


def test_daemon_command_group_exists():
    args = parse_args("daemon", "status")
    assert args.command == "daemon"
    assert args.daemon_action == "status"


@pytest.mark.parametrize(
    ("argv", "expected_action"),
    [
        (("daemon", "start"), "start"),
        (("daemon", "status"), "status"),
        (("daemon", "stop"), "stop"),
        (("up",), "start"),
        (("ps",), "status"),
        (("down",), "stop"),
    ],
)
def test_daemon_lifecycle_commands_parse_to_expected_action(argv, expected_action):
    args = parse_args(*argv)
    assert args.command == "daemon"
    assert args.daemon_action == expected_action


def test_semantic_commands_accept_daemon_mode():
    args = parse_args("find", "Variable", "--daemon", "required")
    assert args.command == "find"
    assert args.daemon_mode == "required"


def test_repl_accepts_daemon_mode():
    args = parse_args("repl", "--daemon", "auto")
    assert args.command == "repl"
    assert args.daemon_mode == "auto"


def test_daemon_status_syncs_top_level_context_from_metadata(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    metadata = {
        "pid": 123,
        "socket_path": "/tmp/demo.sock",
        "active_compdb": str(root / "compile_commands.json"),
        "active_profile": "serial_debug",
        "adapter": "sparta",
    }
    monkeypatch.setattr(daemon_command, "load_metadata", lambda project_root: metadata)
    monkeypatch.setattr(daemon_command, "metadata_is_live", lambda payload: True)

    args = Namespace(project=str(root), daemon_action="status", compdb=None, profile=None)
    context = ExecutionContext.from_namespace(args)
    result = daemon_command.status(args, context)

    assert result.status == "ok"
    assert context.active_compdb == metadata["active_compdb"]
    assert context.active_profile == metadata["active_profile"]
    assert context.adapter == metadata["adapter"]


def test_daemon_start_existing_process_syncs_top_level_context(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    metadata = {
        "pid": 123,
        "socket_path": "/tmp/demo.sock",
        "active_compdb": str(root / "compile_commands.json"),
        "active_profile": None,
        "adapter": "sparta",
    }
    monkeypatch.setattr(daemon_command, "load_metadata", lambda project_root: metadata)
    monkeypatch.setattr(daemon_command, "metadata_is_live", lambda payload: True)

    args = Namespace(project=str(root), daemon_action="start", compdb=None, profile=None)
    context = ExecutionContext.from_namespace(args)
    result = daemon_command.start(args, context)

    assert result.status == "ok"
    assert context.active_compdb == metadata["active_compdb"]
    assert context.adapter == metadata["adapter"]
