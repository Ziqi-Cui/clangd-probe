from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from ..discovery import discover
from ..output import CommandResult


@dataclass
class CompletedCheck:
    returncode: int
    stdout: str
    stderr: str


def find_clangd():
    return shutil.which("clangd")


def run_clangd(argv) -> CompletedCheck:
    completed = subprocess.run(argv, capture_output=True, text=True)
    return CompletedCheck(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run(args, context) -> CommandResult:
    discovery = discover(
        project=getattr(args, "project", None),
        compdb=getattr(args, "compdb", None),
        profile=getattr(args, "profile", None),
    )
    context.apply_discovery(discovery)

    source = Path(args.path).resolve()
    if discovery.status != "ok":
        return CommandResult(
            command="check",
            status="error",
            diagnostics=add_next_step(
                discovery.diagnostics,
                "Provide --compdb explicitly or generate a compilation database first.",
            ),
            warnings=discovery.warnings,
            results=[check_result(source, None, False, None)],
        )

    clangd_path = find_clangd()
    if clangd_path is None:
        return CommandResult(
            command="check",
            status="error",
            diagnostics=[
                {
                    "error_kind": "setup_failure",
                    "message": "clangd is not available on PATH",
                    "next_step": "Install clangd or expose it on PATH before running clangd-probe check.",
                }
            ],
            results=[check_result(source, context.active_compdb, False, None)],
        )

    argv = [
        clangd_path,
        f"--check={source}",
        f"--compile-commands-dir={Path(context.active_compdb).parent}",
    ]
    completed = run_clangd(argv)

    if completed.returncode == 0:
        return CommandResult(
            command="check",
            status="ok",
            results=[check_result(source, context.active_compdb, True, clangd_path, completed.stdout, completed.stderr)],
        )

    return CommandResult(
        command="check",
        status="error",
        diagnostics=[
            {
                "error_kind": "parse_failure",
                "message": summarize_output(completed.stdout, completed.stderr),
                "next_step": parse_failure_next_step(summarize_output(completed.stdout, completed.stderr)),
            }
        ],
        results=[check_result(source, context.active_compdb, False, clangd_path, completed.stdout, completed.stderr)],
    )


def check_result(source, active_compdb, parse_usable, clangd_path, stdout=None, stderr=None):
    payload = {
        "kind": "check",
        "source": str(source),
        "active_compdb": active_compdb,
        "parse_usable": parse_usable,
        "clangd_path": clangd_path,
    }
    if stdout is not None or stderr is not None:
        payload["summary"] = summarize_output(stdout or "", stderr or "")
    return payload


def summarize_output(stdout: str, stderr: str) -> str:
    text = (stdout + "\n" + stderr).strip()
    if not text:
        return "clangd returned no diagnostic output"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("E[") or " error:" in line.lower() or "no such file" in line.lower():
            return line
    return lines[0]


def parse_failure_next_step(summary: str) -> str:
    message = summary.lower()
    if "c++ versions less than c++" in message or "not supported" in message and "c++" in message:
        return (
            "Verify the selected compilation database uses the right C++ standard for this file. "
            "Check the compile command for a suitable -std= flag or project setting such as "
            "CMAKE_CXX_STANDARD, then regenerate compile_commands.json if needed."
        )
    return "Inspect the reported parse error and verify the selected compilation database matches this file."


def add_next_step(diagnostics, next_step):
    updated = []
    for diagnostic in diagnostics:
        entry = dict(diagnostic)
        entry.setdefault("next_step", next_step)
        updated.append(entry)
    return updated
