from __future__ import annotations

import sys

from .cli import ParseFailure, build_parser
from .context import ExecutionContext
from .daemon_client import maybe_route_via_daemon
from .output import parse_failure_result, render_human, render_json


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    context = ExecutionContext()
    result = execute_argv(argv, context)
    if result is None:
        return 0

    if getattr(result, "_print_json", False):
        print(render_json(result, context))
    elif getattr(result, "_already_rendered", False):
        pass
    else:
        print(render_human(result, context))
    return getattr(result, "_exit_code", 0)


def execute_argv(argv, context: ExecutionContext):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except ParseFailure as exc:
        command = detect_command(argv)
        if "--json" in argv:
            result = parse_failure_result(command, exc.message)
            context.__dict__.update(ExecutionContext().__dict__)
            result._print_json = True
        else:
            print(f"{parser.prog}: error: {exc.message}", file=sys.stderr)
            return tagged_result(parse_failure_result(command, exc.message), exit_code=2, already_rendered=True)
        return tagged_result(result, exit_code=2, print_json=True)
    except SystemExit as exc:
        return tagged_result(None, exit_code=int(exc.code), already_rendered=True)

    return execute_args(args, context, parser)


def execute_args(args, context: ExecutionContext, parser=None):
    handler = getattr(args, "command_handler", None)
    if handler is None:
        parser.print_help()
        return tagged_result(None, already_rendered=True)

    updated = ExecutionContext.from_namespace(args)
    context.__dict__.update(updated.__dict__)
    daemon_result = maybe_route_via_daemon(args, context)
    result = daemon_result if daemon_result is not None else handler(args, context)
    context.last_results = list(result.results)
    return tagged_result(
        result,
        exit_code=exit_code_for_status(getattr(result, "status", "ok")),
        print_json=getattr(args, "json_output", False),
    )


def detect_command(argv) -> str:
    for token in argv:
        if not token.startswith("-"):
            return token
    return "global"


def exit_code_for_status(status: str) -> int:
    if status in {"ok", "no_results"}:
        return 0
    if status == "ambiguous":
        return 3
    if status == "unsupported":
        return 4
    return 1


def tagged_result(result, exit_code=0, print_json=False, already_rendered=False):
    if result is None:
        class Empty:
            pass

        result = Empty()
    result._exit_code = exit_code
    result._print_json = print_json
    result._already_rendered = already_rendered
    return result
