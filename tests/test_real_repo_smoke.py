from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.live


def require_live():
    if os.environ.get("CLANGD_CLANGD_PROBE_RUN_LIVE_SMOKE") != "1":
        pytest.skip("live smoke disabled; set CLANGD_CLANGD_PROBE_RUN_LIVE_SMOKE=1")
    if shutil.which("clangd") is None:
        pytest.skip("clangd not available on PATH")


def test_real_repo_smoke_if_compdb_exists():
    require_live()
    repo_root = Path.cwd()
    compdb = repo_root / "build-clangd" / "compile_commands.json"
    if not compdb.exists():
        pytest.skip("real repo smoke requires build-clangd/compile_commands.json")

    env_result = subprocess.run(
        [sys.executable, "-m", "clangd_probe", "env", "--project", str(repo_root), "--profile", "serial_debug", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert env_result.returncode == 0
