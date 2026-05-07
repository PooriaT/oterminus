# User Guide

## First-run Ollama setup

OTerminus requires local Ollama readiness.

Startup checks:

1. `ollama` is available on PATH.
2. Ollama service is reachable (`ollama list`).
3. At least one model is installed.

You can run diagnostics explicitly with:

```bash
poetry run oterminus doctor
```

`doctor` prints the readiness report and exits. It does not start the REPL, execute a request, or
invoke the Ollama planner.

If no model is configured yet, OTerminus shows installed models and prompts you to choose one. The
selection is saved in `~/.oterminus/config.json` (or `OTERMINUS_CONFIG_PATH` if set).

## Model selection behavior

- First run: choose from discovered local models.
- Later runs: saved model is reused.
- If saved model is missing: OTerminus warns and asks for a new selection.

## Running OTerminus

OTerminus has three user-facing CLI entry points:

- REPL mode: `poetry run oterminus`
- one-shot request mode: `poetry run oterminus "show disk usage for this folder"`
- diagnostics mode: `poetry run oterminus doctor`

### REPL mode

```bash
poetry run oterminus
```

REPL mode starts an interactive session after normal startup readiness checks. Requests entered in
the REPL follow the same direct-detection, planning, validation, preview, confirmation, and execution
contract as one-shot requests.

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

One-shot mode accepts the remaining command-line words as a single request. It plans or detects the
command, validates it, renders a preview, and asks for confirmation before execution.

### Doctor mode

```bash
poetry run oterminus doctor
```

Doctor mode is diagnostic-only. It prints readiness and integrity checks, including configuration,
selected model, Ollama CLI/service/model availability, audit path, registry, eval fixture, and
developer-tool status where applicable. It exits with the doctor report status and does not start
the REPL, execute a request, or invoke the Ollama planner.

### Direct commands

You can enter supported command families directly (for example `ls -la`, `cd src`, `pwd`).

Direct commands skip LLM planning when local direct-command detection succeeds. They still pass
through validator + policy gates and show a preview before any execution. In normal execute mode,
they still require confirmation.

### Natural-language requests

You can ask for tasks like:

- “show disk usage for this folder”
- “search TODO in Python files”
- “find processes matching python”

These requests go through capability routing and planning before validation.

## Proposal modes in previews

Previews show the proposal mode so you can understand how OTerminus will handle the command:

- **Structured** is the normal, preferred path. OTerminus uses a curated `command_family` and typed
  `arguments`, then renders the final command deterministically.
- **Experimental** is a constrained fallback for command text that cannot be represented by
  structured arguments yet. It is still strictly validated and requires stronger confirmation.

If validation or policy checks fail, OTerminus does not ask for execution confirmation.

## Safety/inspection modes

### Dry run

```bash
poetry run oterminus --dry-run "copy notes.txt to backup/notes.txt"
```

Runs direct detection or planning, validation, and preview, but does not ask for confirmation or
execute. Direct commands that can be detected locally skip Ollama planning, so a command like
`poetry run oterminus --dry-run "ls"` does not require a live Ollama service. Natural-language
requests still use the planner.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`dry-run <request>` instead.

### Explain mode

```bash
poetry run oterminus --explain "show running processes"
```

Runs direct detection or planning, validation, preview, and an explanation of the command choice and
policy interpretation, but does not ask for confirmation or execute. Direct commands that can be
detected locally skip Ollama planning, so a command like `poetry run oterminus --explain "ls"` does
not require a live Ollama service. Natural-language requests still use the planner.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`explain <request>` or `explain <history_id>` instead.

`--dry-run` and `--explain` are mutually exclusive and apply to requests, not to the `doctor`
diagnostics command. For example, `poetry run oterminus --dry-run doctor` and
`poetry run oterminus doctor --dry-run` are invalid combinations.

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
- Experimental mode is a constrained fallback and requires stronger confirmation.
- Commands that fail validation or policy checks are never executed.
