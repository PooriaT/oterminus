# User Guide

## First-run Ollama setup

OTerminus requires local Ollama readiness.

Startup checks:

1. `ollama` is available on PATH.
2. Ollama service is reachable (`ollama list`).
3. At least one model is installed.

If no model is configured yet, OTerminus shows installed models and prompts you to choose one. The selection is saved in `~/.oterminus/config.json` (or `OTERMINUS_CONFIG_PATH` if set).

## Model selection behavior

- First run: choose from discovered local models.
- Later runs: saved model is reused.
- If saved model is missing: OTerminus warns and asks for a new selection.

## Running OTerminus

### REPL mode

```bash
poetry run oterminus
```

REPL built-ins include:

- `help`, `help capabilities`, `help <capability_id>`, `help <command_family>`
- `capabilities`, `commands`, `examples`, `examples <capability_id>`
- `history`, `history <n>`, `explain <history_id>`, `rerun <history_id>`
- `dry-run <request>`, `explain <request>`
- `audit status`, `exit`, `quit`

### One-shot mode

```bash
poetry run oterminus "find all .py files"
```

### Direct commands

You can enter supported command families directly (for example `ls -la`, `cd src`, `pwd`).

Direct commands skip LLM planning and still pass through validator + policy gates before execution.

### Natural-language requests

You can ask for tasks like:

- “show disk usage for this folder”
- “search TODO in Python files”
- “find processes matching python”

These requests go through capability routing and planning before validation.

## Safety/inspection modes

### Dry run

```bash
poetry run oterminus --dry-run "copy notes.txt to backup/notes.txt"
```

Runs planning + validation + preview, but does not execute.

### Explain mode

```bash
poetry run oterminus --explain "show running processes"
```

Prints command rationale and policy interpretation, but does not execute.

## Autocomplete

REPL supports local tab completion (via `prompt_toolkit`) for:

- built-ins
- supported command families
- capability IDs (and optional capability hints)
- local filesystem paths

## Clear command

`clear` is supported and handled specially by the local executor using ANSI clear-screen output.

## Safety expectations

- OTerminus may block ambiguous broad/destructive requests and suggest safer read-only inspections.
- Unsupported flags, operators, redirection/pipeline chains, and disallowed paths are rejected.
- Experimental mode requires stronger confirmation.
- Commands that fail validation or policy checks are never executed.
