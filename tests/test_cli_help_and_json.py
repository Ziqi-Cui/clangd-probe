import json
import subprocess
import sys


def run_module(*args):
    return subprocess.run(
        [sys.executable, "-m", "clangd_probe", *args],
        capture_output=True,
        text=True,
    )


def parse_json(stdout):
    return json.loads(stdout)


def test_env_help_lists_shared_flags():
    result = run_module("env", "--help")
    assert result.returncode == 0
    text = result.stdout
    for flag in ("--json", "--project", "--compdb", "--profile", "--verbose", "--limit"):
        assert flag in text


def test_env_json_uses_stable_envelope(tmp_path):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "src").mkdir()
    (project_root / "AGENTS.md").write_text("SPARTA repo\n", encoding="utf-8")
    compdb = project_root / "compile_commands.json"
    compdb.write_text("[]", encoding="utf-8")

    result = run_module(
        "env",
        "--json",
        "--project",
        str(project_root),
        "--compdb",
        str(compdb),
        "--profile",
        "serial_debug",
        "--verbose",
        "--limit",
        "7",
    )

    assert result.returncode == 0
    payload = parse_json(result.stdout)
    assert payload["command"] == "env"
    assert payload["status"] == "ok"
    assert payload["project_root"] == str(project_root.resolve())
    assert payload["active_compdb"] == str(compdb.resolve())
    assert payload["active_profile"] == "serial_debug"
    assert payload["adapter"] == "sparta"
    assert payload["backend"] == "clangd"
    assert isinstance(payload["results"], list)
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["diagnostics"], list)
    assert payload["truncated"] is False


def test_json_parse_failure_uses_stable_error_kind():
    result = run_module("env", "--json", "--limit", "not-an-int")
    assert result.returncode != 0
    payload = parse_json(result.stdout)
    assert payload["status"] == "error"
    assert payload["diagnostics"][0]["error_kind"] == "parse_failure"


def test_json_command_error_uses_nonzero_exit_code(tmp_path):
    project_root = tmp_path / "repo"
    project_root.mkdir()

    result = run_module(
        "env",
        "--json",
        "--project",
        str(project_root),
    )

    assert result.returncode != 0
    payload = parse_json(result.stdout)
    assert payload["status"] == "error"
    assert payload["diagnostics"][0]["error_kind"] == "discovery_failure"
