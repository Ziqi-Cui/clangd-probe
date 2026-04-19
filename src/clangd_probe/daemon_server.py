from __future__ import annotations

import atexit
import json
from argparse import Namespace
import signal
import socket
from pathlib import Path

from .commands import check as check_command
from .commands import env as env_command
from .context import ExecutionContext
from .daemon_state import daemon_metadata_path, daemon_socket_path, remove_runtime_files, write_metadata
from .discovery import discover
from .lsp_client import LspClient
from .output import CommandResult


COMMAND_HANDLERS = {
    "env": env_command.run,
    "check": check_command.run,
    "def": __import__("clangd_probe.commands.def", fromlist=["run"]).run,
    "hover": __import__("clangd_probe.commands.hover", fromlist=["run"]).run,
    "symbols": __import__("clangd_probe.commands.symbols", fromlist=["run"]).run,
    "refs": __import__("clangd_probe.commands.refs", fromlist=["run"]).run,
    "find": __import__("clangd_probe.commands.find", fromlist=["run"]).run,
}


class DaemonServer:
    def __init__(self, project_root: Path, compdb: str | None = None, profile: str | None = None):
        self.project_root = Path(project_root).resolve()
        self.explicit_compdb = compdb
        self.profile = profile
        self.socket_path = daemon_socket_path(self.project_root)
        self.metadata_path = daemon_metadata_path(self.project_root)
        self.server = None
        self.client = None
        self.discovery = None
        self.symbol_cache: dict[str, list[object]] = {}
        self.document_symbol_cache: dict[str, list[object]] = {}

    def serve_forever(self) -> int:
        self._prepare_runtime()
        self._install_signal_handlers()
        with self._open_client() as client:
            self.client = client
            self._serve_loop()
        return 0

    def _prepare_runtime(self):
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        remove_runtime_files(self.project_root)
        self.discovery = discover(project=self.project_root, compdb=self.explicit_compdb, profile=self.profile)
        write_metadata(
            self.project_root,
            {
                "pid": os_getpid(),
                "project_root": str(self.project_root),
                "socket_path": str(self.socket_path),
                "active_compdb": str(self.discovery.active_compdb) if self.discovery.active_compdb else None,
                "active_profile": self.discovery.active_profile,
                "adapter": self.discovery.adapter,
            },
        )
        atexit.register(remove_runtime_files, self.project_root)

    def _install_signal_handlers(self):
        def _cleanup_and_exit(signum, frame):
            remove_runtime_files(self.project_root)
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, _cleanup_and_exit)
        signal.signal(signal.SIGINT, _cleanup_and_exit)

    def _open_client(self):
        command = ["clangd"]
        active_compdb = self.discovery.active_compdb if self.discovery else None
        if active_compdb:
            command.append(f"--compile-commands-dir={Path(active_compdb).parent}")
        client = LspClient(command)
        client.start()
        client.initialize(self.project_root, initial_file=self._warm_file())
        return client

    def _warm_file(self):
        active_compdb = self.discovery.active_compdb if self.discovery else None
        if not active_compdb:
            return None
        try:
            payload = json.loads(Path(active_compdb).read_text(encoding="utf-8"))
        except Exception:
            return None
        for entry in payload:
            file_value = entry.get("file")
            if not file_value:
                continue
            path = Path(file_value)
            if not path.is_absolute():
                path = Path(entry.get("directory") or Path(active_compdb).parent) / path
            path = path.resolve()
            if path.exists() and path.suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"}:
                return str(path)
        return None

    def _serve_loop(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            self.server = server
            server.bind(str(self.socket_path))
            server.listen()
            while True:
                conn, _ = server.accept()
                with conn:
                    request = read_json_message(conn)
                    response = self._dispatch_request(request)
                    write_json_message(conn, response)

    def _dispatch_request(self, payload: dict[str, object]) -> dict[str, object]:
        command = str(payload.get("command"))
        args_payload = dict(payload.get("args") or {})
        args_payload["daemon_mode"] = "off"
        args = Namespace(**args_payload)
        context = ExecutionContext.from_namespace(args)
        if self.discovery is not None:
            context.apply_discovery(self.discovery)
        context.backend = "clangd-daemon"
        context.shared_backend = self.client
        context.inside_daemon = True
        context.symbol_cache = self.symbol_cache
        context.document_symbol_cache = self.document_symbol_cache
        handler = COMMAND_HANDLERS[command]
        result = handler(args, context)
        return result.to_envelope(context)


def os_getpid() -> int:
    import os

    return os.getpid()


def read_json_message(conn) -> dict[str, object]:
    stream = conn.makefile("rb")
    payload = stream.readline()
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))


def write_json_message(conn, payload: dict[str, object]) -> None:
    conn.sendall(json.dumps(payload).encode("utf-8") + b"\n")
