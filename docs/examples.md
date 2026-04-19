# clangd-probe Examples

## Installation

```bash
python3 -m pip install -e .
```

## Generic Usage

Inspect the active environment:

```bash
clangd-probe env --project .
```

Ask for JSON output:

```bash
clangd-probe env --json --project .
```

Module form remains available when the console script is not on `PATH`:

```bash
python3 -m clangd_probe env --json --project .
```

Check whether one translation unit can parse with the selected compilation database:

```bash
clangd-probe check src/variable.cpp --project .
```

Find a definition from a location:

```bash
clangd-probe def src/variable.cpp:564:15 --project .
```

Find references from a location:

```bash
clangd-probe refs src/variable.cpp:564:15 --project .
```

List document symbols:

```bash
clangd-probe symbols src/variable.cpp --project .
```

Search workspace symbols:

```bash
clangd-probe find Variable --project . --daemon required --json --limit 10
```

## SPARTA-Oriented Examples

Inspect which compilation database and adapter are active:

```bash
clangd-probe env --project . --profile mpi_debug
```

Check whether the current compilation database matches the file being edited:

```bash
clangd-probe check src/variable.cpp --project . --profile serial_debug
```

Answer “where does this state live?” by pivoting through definition, hover, and references:

```bash
clangd-probe def src/variable.cpp:564:15 --project .
clangd-probe hover src/variable.cpp:564:15 --project .
clangd-probe refs src/variable.cpp:564:15 --project .
```

Warm daemon flow for repeated symbol queries:

```bash
clangd-probe up --project . --json
clangd-probe ps --project . --json
clangd-probe find Variable --project . --daemon required --json --limit 10
clangd-probe def Variable::next --project . --daemon required --json
clangd-probe hover Variable::next --project . --daemon required --json
clangd-probe refs Variable::next --project . --daemon required --json
clangd-probe down --project . --json
```

## REPL

Start one interactive session:

```bash
clangd-probe repl --project .
```

Inside the REPL:

```text
env
def src/variable.cpp:564:15
refs @last
hover src/variable.cpp:564:15
find Variable
quit
```

`@last` reuses the most recent location-like result. Run `refs @last` before a
command such as `hover` that replaces it with non-location output.
