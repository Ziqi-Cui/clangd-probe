from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import time


def daemon_dir(project_root) -> Path:
    return Path(project_root).resolve() / ".cache" / "clangd_probe"


def daemon_socket_path(project_root) -> Path:
    resolved = Path(project_root).resolve()
    suffix = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"clangd_probe_{suffix}.sock"


def daemon_metadata_path(project_root) -> Path:
    return daemon_dir(project_root) / "daemon.json"


def encode_request(payload: dict[str, object]) -> bytes:
    return json.dumps(payload).encode("utf-8")


def decode_message(payload: bytes) -> dict[str, object]:
    return json.loads(payload.decode("utf-8"))


def metadata_is_live(metadata: dict[str, object]) -> bool:
    pid = metadata.get("pid")
    socket_path = metadata.get("socket_path")
    if not isinstance(pid, int) or not isinstance(socket_path, str):
        return False
    if not Path(socket_path).exists():
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def load_metadata(project_root) -> dict[str, object] | None:
    path = daemon_metadata_path(project_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_metadata(project_root, payload: dict[str, object]) -> Path:
    path = daemon_metadata_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def remove_runtime_files(project_root) -> None:
    for path in (daemon_socket_path(project_root), daemon_metadata_path(project_root)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def wait_for_socket(project_root, timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    socket_path = daemon_socket_path(project_root)
    metadata_path = daemon_metadata_path(project_root)
    while time.time() < deadline:
        if socket_path.exists() and metadata_path.exists():
            return True
        time.sleep(0.05)
    return False


def stop_metadata_process(metadata: dict[str, object]) -> bool:
    pid = metadata.get("pid")
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True
