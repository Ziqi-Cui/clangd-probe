# clangd-probe

Agent-friendly command-line front-end for `clangd`.

`clangd-probe` is a terminal-first wrapper around real `clangd` and real
`compile_commands.json` data. It is built for coding agents and humans who need
reliable semantic navigation from the shell without scraping editor state.

## What It Is

`clangd-probe` keeps the actual language server in the loop, but adds a more
automation-friendly contract on top:

- stable JSON envelopes with explicit `status`, `diagnostics`, and `results`
- non-zero exit codes for command errors
- explicit repository and compilation-database selection with `--project` and
  `--compdb`
- a project-local warm daemon for repeated symbol queries

It is useful when an agent needs to answer questions like:

- can this translation unit parse with the selected compilation database?
- where is this symbol defined?
- what does clangd think this location means?
- can I reuse a warm semantic session instead of cold-starting `clangd` each time?

## Why It Matters

Compared with calling `clangd` directly, this wrapper gives agents a cleaner CLI
surface:

- `env` makes discovery state explicit before deeper semantic calls
- `check` turns parse viability into a stable command contract
- semantic commands can take either a location or a symbol query
- daemon-backed routing makes repeated symbol work much faster
- failures are structured instead of relying on raw stderr parsing

## Install

```bash
python3 -m pip install -e .
```

Python module entrypoint:

```bash
python3 -m clangd_probe --help
```

CLI entrypoint:

```bash
clangd-probe --help
```

## Agent Contract

For automation and agent use:

- prefer `--json`
  The JSON envelope is the machine-safe surface.
- pass `--project <path>` explicitly
  Avoid accidental cwd-based discovery changes.
- pass `--compdb <path>` when the active compilation database is not obvious
- use `--daemon required` for deterministic warm-daemon symbol queries
  `auto` is convenient for humans; `required` is clearer for agents.

Top-level statuses:

- `ok`
- `no_results`
- `ambiguous`
- `unsupported`
- `error`

Error diagnostics use stable kinds:

- `setup_failure`
- `discovery_failure`
- `parse_failure`
- `internal_failure`

Exit behavior:

- `ok` and `no_results` exit `0`
- command errors exit non-zero
- parse/CLI errors also exit non-zero

## Quick Start

Start with discovery and parse viability:

```bash
clangd-probe env --project . --json
clangd-probe check path/to/file.cpp --project . --json
```

Then move into semantic queries:

```bash
clangd-probe def path/to/file.cpp:120:7 --project . --json
clangd-probe hover path/to/file.cpp:120:7 --project . --json
clangd-probe refs path/to/file.cpp:120:7 --project . --json
```

For repeated symbol queries, use the warm daemon:

```bash
clangd-probe up --project . --json
clangd-probe find Variable --project . --daemon required --json --limit 10
clangd-probe def Variable::next --project . --daemon required --json
clangd-probe hover Variable::next --project . --daemon required --json
clangd-probe refs Variable::next --project . --daemon required --json
clangd-probe down --project . --json
```

Module-form fallback remains available:

```bash
python3 -m clangd_probe daemon start --project .
python3 -m clangd_probe daemon stop --project .
```

## Commands

- `env`
  Inspect discovery, active compilation database, adapter choice, and whether
  `clangd` is available.
- `check <file>`
  Run a friendlier `clangd --check` flow for one source file.
- `def <symbol-or-location>`
  Find a definition from `file:line[:col]` or a symbol query.
- `hover <symbol-or-location>`
  Show semantic hover content.
- `symbols <file>`
  List document symbols for one file.
- `refs <symbol-or-location>`
  Find references from a location or semantic symbol resolution.
- `find <query>`
  Query workspace symbols without falling back to grep.
- `daemon <start|status|stop>`
  Manage the project-local warm `clangd-probe` daemon.
- `up | ps | down`
  Short aliases for `daemon start | status | stop`.
- `repl`
  Reuse one execution context for repeated navigation commands.

## Shared Flags

- `--json`
  Preferred for automation and agent use. Emits the stable machine-readable envelope.
- `--project <path>`
  Project root used for discovery and daemon scoping.
- `--compdb <path>`
  Explicit `compile_commands.json` path.
- `--profile <name>`
  Optional adapter-specific discovery profile when the repository supports one.
- `--verbose`
- `--limit <n>`
- `--daemon <auto|off|required>`
  Use `required` when an agent needs deterministic warm-daemon routing instead of silent fallback.

## Repository Notes

`clangd-probe` is written to be repository-agnostic. It works best anywhere a
real compilation database can be discovered or passed explicitly.

Some repositories may still have adapter-specific discovery helpers or profile
conventions. Treat those as optional repository-local details, not the main
contract of this tool.

## Skill

The companion operations skill is here:

- [skills/clangd-probe-operations/SKILL.md](./skills/clangd-probe-operations/SKILL.md)

Use it when you want a repeatable validation or production smoke flow instead of
choosing commands ad hoc.

## Examples

See [docs/examples.md](./docs/examples.md) for end-to-end examples.
