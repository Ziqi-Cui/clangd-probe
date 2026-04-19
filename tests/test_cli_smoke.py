import subprocess
import sys


def run_module(*args):
    return subprocess.run(
        [sys.executable, "-m", "clangd_probe", *args],
        capture_output=True,
        text=True,
    )


def test_help_renders():
    result = run_module("--help")
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    for flag in ("--json", "--project", "--compdb", "--profile", "--verbose", "--limit", "--daemon"):
        assert flag in result.stdout


def test_unknown_command_fails_cleanly():
    result = run_module("unknown-command")
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "invalid choice" in combined or "unrecognized arguments" in combined
