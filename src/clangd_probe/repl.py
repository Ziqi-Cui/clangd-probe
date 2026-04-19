from __future__ import annotations

import shlex

from .context import ExecutionContext


def normalize_last(tokens, context):
    if "@last" not in tokens or not context.last_results:
        return tokens
    first = context.last_results[0]
    if all(key in first for key in ("path", "line", "column")):
        replacement = f"{first['path']}:{first['line']}:{first['column']}"
        return [replacement if token == "@last" else token for token in tokens]
    return tokens


def run_session(lines, context: ExecutionContext, dispatch):
    transcript = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line in {"quit", "exit"}:
            break
        tokens = normalize_last(shlex.split(line), context)
        result = dispatch(tokens, context)
        context.last_results = list(result.results)
        transcript.append(result.to_envelope(context))
    return transcript


def run(args, context):
    from .main import execute_argv

    def dispatch(tokens, current_context):
        return execute_argv(tokens, current_context)

    while True:
        try:
            line = input("clangd-clangd-probe> ")
        except EOFError:
            break
        transcript = run_session([line], context, dispatch)
        if not transcript:
            if line.strip() in {"quit", "exit"}:
                break
            continue
        payload = transcript[-1]
        if getattr(args, "json_output", False):
            print(render_json_from_payload(payload))
        else:
            print(render_human_from_payload(payload))
    from .output import CommandResult

    return CommandResult(command="repl", status="ok", results=[])


def render_json_from_payload(payload):
    import json

    return json.dumps(payload, indent=2, sort_keys=True)


def render_human_from_payload(payload):
    lines = [
        f"command: {payload['command']}",
        f"status: {payload['status']}",
    ]
    return "\n".join(lines)
