from __future__ import annotations

import json
import socket
from pathlib import Path

from .daemon_state import daemon_metadata_path, daemon_socket_path, load_metadata, metadata_is_live
from .output import CommandResult


DAEMON_CAPABLE_COMMANDS = {"find", "def", "hover", "refs", "symbols"}
DAEMON_REQUEST_TIMEOUT_S = 3.0


def maybe_route_via_daemon(args, context):
    command = getattr(args, "command", None)
    if command not in DAEMON_CAPABLE_COMMANDS:
        return None
    if getattr(context, "inside_daemon", False):
        return None

    mode = getattr(args, "daemon_mode", "auto")
    if mode == "off":
        return None

    project_root = Path(getattr(args, "project", None) or context.project_root or Path.cwd()).resolve()
    metadata = load_metadata(project_root)
    if metadata is None or not metadata_is_live(metadata):
        if mode == "required":
            return CommandResult(
                command=command,
                status="error",
                diagnostics=[
                    {
                        "error_kind": "setup_failure",
                        "message": "required daemon is not running for this project",
                        "next_step": "Start it with `clangd-probe daemon start --project .`.",
                    }
                ],
            )
        return None

    try:
        envelope = send_request(
            project_root,
            {
                "command": command,
                "args": namespace_payload(args),
            },
        )
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        if mode == "required":
            return daemon_transport_failure(command, exc)
        return None
    apply_envelope_context(context, envelope)
    return result_from_envelope(envelope)


def namespace_payload(args):
    payload = dict(vars(args))
    payload.pop("command_handler", None)
    return payload


def send_request(project_root, payload: dict[str, object]) -> dict[str, object]:
    socket_path = daemon_socket_path(project_root)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(DAEMON_REQUEST_TIMEOUT_S)
        client.connect(str(socket_path))
        client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
        stream = client.makefile("rb")
        return json.loads(stream.readline().decode("utf-8"))


def result_from_envelope(envelope: dict[str, object]) -> CommandResult:
    return CommandResult(
        command=str(envelope.get("command")),
        status=str(envelope.get("status", "error")),
        results=list(envelope.get("results") or []),
        warnings=list(envelope.get("warnings") or []),
        diagnostics=list(envelope.get("diagnostics") or []),
        truncated=bool(envelope.get("truncated", False)),
    )


def apply_envelope_context(context, envelope: dict[str, object]) -> None:
    context.project_root = envelope.get("project_root")
    context.active_compdb = envelope.get("active_compdb")
    context.active_profile = envelope.get("active_profile")
    context.adapter = envelope.get("adapter", context.adapter)
    context.backend = envelope.get("backend", context.backend)


def daemon_transport_failure(command: str, exc: Exception) -> CommandResult:
    return CommandResult(
        command=command,
        status="error",
        diagnostics=[
            {
                "error_kind": "setup_failure",
                "message": f"daemon request failed: {exc}",
                "next_step": "Restart it with `clangd-probe down --project .` and `clangd-probe up --project .`, or retry with `--daemon off`.",
            }
        ],
    )
