# Contributing

## Setup

Install the project in editable mode:

```bash
python3 -m pip install -e .
```

## Tests

Run the core test suite from the repository root:

```bash
PYTHONPATH=src pytest -q
```

If you are only touching a narrow area, run the most relevant focused tests in
addition to the full suite when practical.

## Documentation

Keep the README, examples, and the operations skill aligned with the actual CLI
behavior.

For automation-oriented examples:

- prefer `--json`
- prefer explicit `--project`
- prefer `--daemon required` when the example relies on warm-daemon behavior

## Scope

Favor small, behaviorally clear changes. If a change alters the CLI contract,
update tests and documentation together.
