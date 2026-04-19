from __future__ import annotations

import pytest

from clangd_probe.cli import build_parser


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
