from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

from clangd_probe.context import ExecutionContext
from clangd_probe import daemon_client
from clangd_probe.daemon_client import maybe_route_via_daemon


def make_args(**overrides):
    base = {
        "command": "find",
        "query": "Variable",
        "project": "/tmp/demo",
        "compdb": None,
        "profile": None,
        "verbose": False,
        "limit": 10,
        "json_output": False,
        "daemon_mode": "required",
    }
    base.update(overrides)
    return Namespace(**base)


def test_required_daemon_reports_structured_error(monkeypatch):
    args = make_args()
    context = ExecutionContext.from_namespace(args)

    monkeypatch.setattr("clangd_probe.daemon_client.load_metadata", lambda project_root: None)

    result = maybe_route_via_daemon(args, context)

    assert result is not None
    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "setup_failure"


def test_daemon_response_updates_context(monkeypatch):
    args = make_args()
    context = ExecutionContext.from_namespace(args)

    monkeypatch.setattr(
        "clangd_probe.daemon_client.load_metadata",
        lambda project_root: {"pid": 1, "socket_path": "/tmp/demo.sock"},
    )
    monkeypatch.setattr("clangd_probe.daemon_client.metadata_is_live", lambda metadata: True)
    monkeypatch.setattr(
        "clangd_probe.daemon_client.send_request",
        lambda project_root, payload: {
            "command": "find",
            "status": "ok",
            "project_root": "/tmp/demo",
            "active_compdb": "/tmp/demo/compile_commands.json",
            "active_profile": None,
            "adapter": "sparta",
            "backend": "clangd-daemon",
            "results": [{"name": "Variable"}],
            "warnings": [],
            "diagnostics": [],
            "truncated": False,
        },
    )

    result = maybe_route_via_daemon(args, context)

    assert result is not None
    assert result.status == "ok"
    assert context.active_compdb == "/tmp/demo/compile_commands.json"
    assert context.adapter == "sparta"
    assert context.backend == "clangd-daemon"


def test_required_daemon_transport_failure_reports_structured_error(monkeypatch):
    args = make_args(daemon_mode="required")
    context = ExecutionContext.from_namespace(args)

    monkeypatch.setattr(
        "clangd_probe.daemon_client.load_metadata",
        lambda project_root: {"pid": 1, "socket_path": "/tmp/demo.sock"},
    )
    monkeypatch.setattr("clangd_probe.daemon_client.metadata_is_live", lambda metadata: True)
    monkeypatch.setattr(
        "clangd_probe.daemon_client.send_request",
        lambda project_root, payload: (_ for _ in ()).throw(ConnectionRefusedError("boom")),
    )

    result = maybe_route_via_daemon(args, context)

    assert result is not None
    assert result.status == "error"
    assert result.diagnostics[0]["error_kind"] == "setup_failure"
    assert "daemon request failed" in result.diagnostics[0]["message"]


def test_auto_daemon_transport_failure_falls_back_to_local_handler(monkeypatch):
    args = make_args(daemon_mode="auto")
    context = ExecutionContext.from_namespace(args)

    monkeypatch.setattr(
        "clangd_probe.daemon_client.load_metadata",
        lambda project_root: {"pid": 1, "socket_path": "/tmp/demo.sock"},
    )
    monkeypatch.setattr("clangd_probe.daemon_client.metadata_is_live", lambda metadata: True)
    monkeypatch.setattr(
        "clangd_probe.daemon_client.send_request",
        lambda project_root, payload: (_ for _ in ()).throw(ConnectionResetError("boom")),
    )

    result = maybe_route_via_daemon(args, context)

    assert result is None


def test_send_request_sets_socket_timeout(monkeypatch):
    calls = {}

    class FakeStream:
        def readline(self):
            return json.dumps({"command": "find", "status": "ok"}).encode("utf-8") + b"\n"

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def settimeout(self, value):
            calls["timeout"] = value

        def connect(self, path):
            calls["connect"] = path

        def sendall(self, payload):
            calls["payload"] = payload

        def makefile(self, mode):
            calls["mode"] = mode
            return FakeStream()

    monkeypatch.setattr("clangd_probe.daemon_client.daemon_socket_path", lambda project_root: Path("/tmp/demo.sock"))
    monkeypatch.setattr("clangd_probe.daemon_client.socket.socket", lambda *args: FakeSocket())

    envelope = daemon_client.send_request(Path("/tmp/demo"), {"command": "find"})

    assert envelope["status"] == "ok"
    assert calls["timeout"] == daemon_client.DAEMON_REQUEST_TIMEOUT_S
