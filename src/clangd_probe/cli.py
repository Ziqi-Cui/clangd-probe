from __future__ import annotations

import argparse
import importlib

from .commands import daemon as daemon_command
from .commands import check as check_command
from .commands import env as env_command


class ParseFailure(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class FrontendArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ParseFailure(message)


def add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="json_output", help="emit the machine-readable JSON envelope")
    parser.add_argument("--project", help="project root used for discovery and daemon scoping")
    parser.add_argument("--compdb", help="explicit compile_commands.json path")
    parser.add_argument("--profile", help="adapter-specific discovery profile")
    parser.add_argument("--verbose", action="store_true", help="include more diagnostic detail where available")
    parser.add_argument("--limit", type=int, help="limit result count for commands that support truncation")
    parser.add_argument(
        "--daemon",
        dest="daemon_mode",
        choices=["auto", "off", "required"],
        default="auto",
        help="daemon routing mode; use 'required' for deterministic warm-daemon symbol queries",
    )


def build_parser() -> FrontendArgumentParser:
    def_command = importlib.import_module("clangd_probe.commands.def")
    hover_command = importlib.import_module("clangd_probe.commands.hover")
    symbols_command = importlib.import_module("clangd_probe.commands.symbols")
    refs_command = importlib.import_module("clangd_probe.commands.refs")
    find_command = importlib.import_module("clangd_probe.commands.find")

    parser = FrontendArgumentParser(
        prog="clangd-probe",
        description="Reusable command-line front-end for clangd.",
        epilog=(
            "Shared flags: --json --project --compdb --profile --verbose --limit "
            "--daemon. Short daemon aliases: up=start, ps=status, down=stop."
        ),
    )
    add_shared_arguments(parser)
    subparsers = parser.add_subparsers(dest="command")

    shared = argparse.ArgumentParser(add_help=False)
    add_shared_arguments(shared)

    env_parser = subparsers.add_parser(
        "env",
        parents=[shared],
        help="inspect frontend environment",
    )
    env_parser.set_defaults(command_handler=env_command.run)

    check_parser = subparsers.add_parser(
        "check",
        parents=[shared],
        help="run a clangd parse check for one source file",
    )
    check_parser.add_argument("path")
    check_parser.set_defaults(command_handler=check_command.run)

    def_parser = subparsers.add_parser("def", parents=[shared], help="find a definition from a location or symbol")
    def_parser.add_argument("target")
    def_parser.set_defaults(command_handler=def_command.run)

    hover_parser = subparsers.add_parser("hover", parents=[shared], help="show hover information from a location or symbol")
    hover_parser.add_argument("target")
    hover_parser.set_defaults(command_handler=hover_command.run)

    symbols_parser = subparsers.add_parser("symbols", parents=[shared], help="list document symbols")
    symbols_parser.add_argument("path")
    symbols_parser.set_defaults(command_handler=symbols_command.run)

    refs_parser = subparsers.add_parser("refs", parents=[shared], help="find references from a location or symbol")
    refs_parser.add_argument("target")
    refs_parser.set_defaults(command_handler=refs_command.run)

    find_parser = subparsers.add_parser("find", parents=[shared], help="search workspace symbols")
    find_parser.add_argument("query")
    find_parser.set_defaults(command_handler=find_command.run)

    repl_parser = subparsers.add_parser("repl", parents=[shared], help="start an interactive semantic session")
    repl_parser.set_defaults(command_handler=run_repl_command)

    daemon_parser = subparsers.add_parser("daemon", help="manage the project-local clangd-probe daemon")
    daemon_subparsers = daemon_parser.add_subparsers(dest="daemon_action")

    daemon_start = daemon_subparsers.add_parser("start", parents=[shared], help="start the local daemon")
    daemon_start.set_defaults(command_handler=daemon_command.run)

    daemon_status = daemon_subparsers.add_parser("status", parents=[shared], help="inspect daemon status")
    daemon_status.set_defaults(command_handler=daemon_command.run)

    daemon_stop = daemon_subparsers.add_parser("stop", parents=[shared], help="stop the local daemon")
    daemon_stop.set_defaults(command_handler=daemon_command.run)

    daemon_serve = daemon_subparsers.add_parser("serve", parents=[shared], help=argparse.SUPPRESS)
    daemon_serve.set_defaults(command_handler=daemon_command.run)

    def add_daemon_alias(name: str, action: str, help_text: str):
        alias_parser = subparsers.add_parser(name, parents=[shared], help=help_text)
        alias_parser.set_defaults(command="daemon", daemon_action=action, command_handler=daemon_command.run)

    add_daemon_alias("up", "start", "start the local daemon")
    add_daemon_alias("ps", "status", "inspect daemon status")
    add_daemon_alias("down", "stop", "stop the local daemon")

    return parser


def run_repl_command(args, context):
    repl_module = importlib.import_module("clangd_probe.repl")
    return repl_module.run(args, context)
