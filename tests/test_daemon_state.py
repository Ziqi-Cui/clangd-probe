from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile

from clangd_probe.daemon_state import (
    daemon_dir,
    daemon_metadata_path,
    daemon_socket_path,
    encode_request,
    decode_message,
    metadata_is_live,
)


def test_daemon_paths_live_under_project_cache(tmp_path):
    assert daemon_dir(tmp_path) == tmp_path / ".cache" / "clangd_probe"
    assert daemon_metadata_path(tmp_path) == tmp_path / ".cache" / "clangd_probe" / "daemon.json"
    suffix = hashlib.sha1(str(tmp_path.resolve()).encode("utf-8")).hexdigest()[:12]
    assert daemon_socket_path(tmp_path) == Path(tempfile.gettempdir()) / f"clangd_probe_{suffix}.sock"


def test_request_round_trip_is_json_stable():
    payload = {"command": "find", "args": {"query": "Variable"}, "request_id": "abc"}
    encoded = encode_request(payload)
    decoded = decode_message(encoded)
    assert decoded == payload


def test_metadata_is_live_rejects_missing_process(tmp_path):
    metadata = {"pid": 999999, "socket_path": str(tmp_path / "daemon.sock")}
    assert metadata_is_live(metadata) is False


def test_metadata_is_live_accepts_current_process(tmp_path):
    socket_path = tmp_path / "daemon.sock"
    socket_path.write_text("", encoding="utf-8")
    metadata = {"pid": os.getpid(), "socket_path": str(socket_path)}
    assert metadata_is_live(metadata) is True
