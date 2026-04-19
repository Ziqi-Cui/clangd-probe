# clangd-probe Production Notes

## Goal

Use `clangd-probe` against a real repository without guessing which discovery or
setup step is missing.

## Preconditions

- `clangd` is on `PATH`
- the repository has a usable `compile_commands.json`
- for SPARTA-style repositories, the compilation database should normally be
  prepared before semantic commands are attempted

## SPARTA Setup

If `env` or `check` reports:

```text
no compile_commands.json candidates found
```

the first recovery step is:

```bash
tools/dev/setup_clangd.sh serial_debug
```

Alternative profiles:

- `tools/dev/setup_clangd.sh mpi_debug`
- `tools/dev/setup_clangd.sh kokkos_omp`

That helper expands the generated compilation database to the repository root as
`compile_commands.json`.

## Production Smoke Ladder

Run in this order:

```bash
clangd-probe env --project . --json
clangd-probe check src/variable.cpp --project . --json
clangd-probe def src/variable.cpp:564:15 --project . --json
clangd-probe hover src/variable.cpp:564:15 --project . --json
clangd-probe refs src/variable.cpp:564:15 --project . --json
```

For faster symbol-oriented queries in repeated real-world use, prefer the warm
daemon path:

```bash
clangd-probe up --project .
clangd-probe ps --project . --json
clangd-probe find Variable --project . --daemon required --json --limit 10
clangd-probe def Variable::next --project . --daemon required --json
clangd-probe hover Variable::next --project . --daemon required --json
clangd-probe refs Variable::next --project . --daemon required --json
clangd-probe down --project .
```

Only move past `env` after the active compilation database is explicit and
credible.

## Common Failure Modes

- `setup_failure`
  `clangd` is missing from `PATH`
- `discovery_failure`
  no compilation database, ambiguous candidates, unknown profile
- `parse_failure`
  the selected compilation database does not parse the requested file cleanly
- `required daemon is not running`
  start the project-local daemon before using `--daemon required`

## CLI vs Module

Both are supported and tested:

```bash
clangd-probe --help
python3 -m clangd_probe --help
```
