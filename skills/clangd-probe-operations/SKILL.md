---
name: clangd-probe-operations
description: Use when validating, troubleshooting, or demonstrating clangd-probe in a real C/C++ repository, especially when an agent needs a repeatable env/check/semantic smoke flow.
---

# clangd-probe Operations

## When To Use

Use this skill when you need to:

- verify `clangd-probe` works in a real repository
- diagnose why `env` or `check` fails
- prepare a repository for semantic commands
- run a short production smoke ladder before release
- drive semantic queries in a way that is safe for automation

## Workflow

1. Check the entrypoints:
   - `clangd-probe --help`
   - `python3 -m clangd_probe --help`
2. Check environment discovery:
   - `clangd-probe env --project . --json`
3. If discovery fails because no compilation database exists, fix that before
   semantic commands:
   - point `--compdb` at the right `compile_commands.json`, or
   - generate one with the repository's normal build tooling
4. Re-run:
   - `clangd-probe env --project . --json`
   - `clangd-probe check <file> --project . --json`
5. Only after `env` and `check` look credible, run semantic commands:
   - `def`
   - `hover`
   - `refs`
   - `symbols`
   - `find`
6. For repeated symbol queries, prefer the warm daemon:
   - `clangd-probe up --project . --json`
   - then run symbol queries with `--daemon required --json`
   - inspect it with `clangd-probe ps --project . --json`
   - read `results[0].metadata` for the daemon's active compdb and adapter
   - stop it with `clangd-probe down --project . --json`

If the console script is unavailable, the module form remains supported.

## Generic Defaults

- prefer `--json` for anything an agent might parse
- prefer explicit `--project`
- prefer explicit `--compdb` when discovery is not obvious
- prefer `--daemon required` for repeatable warm-daemon symbol queries

## Repository-Specific Fallbacks

Some repositories provide helper scripts or named build profiles to produce
`compile_commands.json`. Use those when needed, but treat them as repository
local setup, not as the main `clangd-probe` workflow.

## Failure Interpretation

- `setup_failure`: fix tool availability first
- `discovery_failure`: fix compilation database selection before semantic use
- `parse_failure`: the chosen compilation database does not match the file well enough
- `error` + non-zero exit: treat as command failure in automation

## Production Smoke

Use this exact order with a file and location that already passed `check`:

```bash
clangd-probe env --project . --json
clangd-probe check path/to/file.cpp --project . --json
clangd-probe def path/to/file.cpp:line:col --project . --json
clangd-probe hover path/to/file.cpp:line:col --project . --json
clangd-probe refs path/to/file.cpp:line:col --project . --json
```

For hot symbol queries:

```bash
clangd-probe up --project . --json
clangd-probe ps --project . --json
clangd-probe find Variable --project . --daemon required --json --limit 10
clangd-probe def Variable::next --project . --daemon required --json
clangd-probe hover Variable::next --project . --daemon required --json
clangd-probe refs Variable::next --project . --daemon required --json
clangd-probe down --project . --json
```
