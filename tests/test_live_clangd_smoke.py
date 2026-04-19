from __future__ import annotations

import json
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


def write_fixture_project(root: Path):
    source = root / "demo.cpp"
    source.write_text("int demo() { return 0; }\nint main() { return demo(); }\n", encoding="utf-8")
    compdb = root / "compile_commands.json"
    compdb.write_text(
        json.dumps(
            [
                {
                    "directory": str(root.resolve()),
                    "command": f"clang++ -std=c++17 -c {source.name}",
                    "file": str(source.resolve()),
                }
            ]
        ),
        encoding="utf-8",
    )
    return source


def test_live_fixture_env_and_check(tmp_path):
    require_live()
    source = write_fixture_project(tmp_path)

    env_result = subprocess.run(
        [sys.executable, "-m", "clangd_probe", "env", "--project", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert env_result.returncode == 0

    check_result = subprocess.run(
        [sys.executable, "-m", "clangd_probe", "check", str(source), "--project", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert check_result.returncode == 0
