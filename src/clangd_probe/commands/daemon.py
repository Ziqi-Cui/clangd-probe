from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time

from ..context import ExecutionContext
from ..daemon_server import DaemonServer
from ..daemon_state import (
    daemon_dir,
    daemon_metadata_path,
    daemon_socket_path,
    load_metadata,
    metadata_is_live,
    remove_runtime_files,
    stop_metadata_process,
    wait_for_socket,
)
from ..output import CommandResult


def run(args, context: ExecutionContext) -> CommandResult:
    action = getattr(args, "daemon_action", None)
    if action == "start":
        return start(args, context)
    if action == "status":
        return status(args, context)
    if action == "stop":
        return stop(args, context)
    if action == "serve":
        return serve(args, context)
    return CommandResult(
        command="daemon",
        status="error",
        diagnostics=[{"error_kind": "setup_failure", "message": f"unknown daemon action: {action}"}],
    )


def _project_root(args, context: ExecutionContext) -> Path:
    if getattr(args, "project", None):
        return Path(args.project).resolve()
    if context.project_root:
        return Path(context.project_root).resolve()
    return Path.cwd()


def start(args, context: ExecutionContext) -> CommandResult:
    root = _project_root(args, context)
    cache_dir = daemon_dir(root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    socket_path = daemon_socket_path(root)
    metadata_path = daemon_metadata_path(root)
    metadata = load_metadata(root)
    if metadata is not None and metadata_is_live(metadata):
        return CommandResult(
            command="daemon",
            status="ok",
            results=[
                {
                    "kind": "daemon",
                    "action": "start",
                    "project_root": str(root),
                    "socket_path": str(socket_path),
                    "metadata_path": str(metadata_path),
                    "running": True,
                    "pid": metadata.get("pid"),
                }
            ],
        )

    remove_runtime_files(root)
    argv = [
        sys.executable,
        "-m",
        "clangd_probe",
        "daemon",
        "serve",
        "--project",
        str(root),
    ]
    if getattr(args, "compdb", None):
        argv.extend(["--compdb", str(args.compdb)])
    if getattr(args, "profile", None):
        argv.extend(["--profile", str(args.profile)])
    subprocess.Popen(
        argv,
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    ready = wait_for_socket(root, timeout_s=5.0)
    payload = {
        "kind": "daemon",
        "action": "start",
        "project_root": str(root),
        "socket_path": str(socket_path),
        "metadata_path": str(metadata_path),
        "running": ready,
    }
    status = "ok" if ready else "error"
    diagnostics = []
    if not ready:
        diagnostics.append(
            {
                "error_kind": "setup_failure",
                "message": "daemon did not become ready within 5 seconds",
                "next_step": "Inspect the project environment and retry `clangd-probe daemon start --project .`.",
            }
        )
    return CommandResult(command="daemon", status=status, results=[payload], diagnostics=diagnostics)


def status(args, context: ExecutionContext) -> CommandResult:
    root = _project_root(args, context)
    metadata_path = daemon_metadata_path(root)
    socket_path = daemon_socket_path(root)
    live = False
    metadata = None
    metadata = load_metadata(root)
    if metadata is not None:
        live = metadata_is_live(metadata)
    payload = {
        "kind": "daemon",
        "action": "status",
        "project_root": str(root),
        "socket_path": str(socket_path),
        "metadata_path": str(metadata_path),
        "running": live,
        "metadata": metadata,
    }
    return CommandResult(command="daemon", status="ok", results=[payload])


def stop(args, context: ExecutionContext) -> CommandResult:
    root = _project_root(args, context)
    metadata = load_metadata(root)
    stopped = False
    if metadata is not None:
        stopped = stop_metadata_process(metadata)
        deadline = time.time() + 5.0
        while time.time() < deadline:
            refreshed = load_metadata(root)
            if refreshed is None or not metadata_is_live(refreshed):
                break
            time.sleep(0.05)
    remove_runtime_files(root)
    payload = {
        "kind": "daemon",
        "action": "stop",
        "project_root": str(root),
        "socket_path": str(daemon_socket_path(root)),
        "metadata_path": str(daemon_metadata_path(root)),
        "stopped": stopped or metadata is None,
    }
    return CommandResult(command="daemon", status="ok", results=[payload])


def serve(args, context: ExecutionContext) -> CommandResult:
    server = DaemonServer(
        project_root=_project_root(args, context),
        compdb=getattr(args, "compdb", None),
        profile=getattr(args, "profile", None),
    )
    raise SystemExit(server.serve_forever())
