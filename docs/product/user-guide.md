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

REPL mode starts an interactive session. Requests entered in the REPL follow the same lifecycle as
one-shot requests: direct-command detection, natural-language ambiguity handling when applicable,
planning for specific natural-language requests, validation, preview, confirmation, execution, and
audit logging.

REPL built-ins include (all local, deterministic, and backed by command-registry metadata; they do not call Ollama):

- `help`, `help capabilities`, `help <capability_id>`, `help <command_family>`
- `capabilities`, `commands`, `examples`
- `history`, `history <n>`, `explain <history_id>`, `rerun <history_id>`
- `dry-run <request>`, `explain <request>`
- `audit status`, `exit`, `quit`

### One-shot mode

```bash
poetry run oterminus "find all .py files"
```

One-shot mode accepts the remaining command-line words as a single request. It detects direct
commands first, checks non-direct natural-language requests for ambiguity, plans specific
natural-language requests, validates accepted proposals, renders a preview, and asks for
confirmation before execution.

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

These requests first pass through ambiguity detection. If the request is specific enough, it goes
through capability routing and planning before validation.

### Ambiguous natural-language requests

OTerminus may stop vague natural-language requests before any planner call. Examples include:

```text
clean this folder
delete unnecessary files
repair permissions
make this project work
```

Expected behavior:

- OTerminus stops before planning.
- It shows that the request is ambiguous and includes the reason when useful.
- It suggests safe read-only inspection alternatives, such as listing large files, recently modified
  files, temporary-looking files, project files, or inspecting permissions.
- It does not ask for confirmation and does not execute anything.

Use a more specific request when you know the target and action. Specific requests can continue to
routing, planning, validation, preview, and confirmation, for example:

```text
list large files in this folder
show permissions for run.sh
make run.sh executable
```

Ambiguity detection is only for vague natural-language requests. Direct shell commands such as
`chmod +x run.sh` or `rm -rf build` are not intercepted as ambiguous; they continue to the direct
command path and must still pass validator and policy checks before any execution.

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

Dry run is a safety preview for checking what OTerminus would do. It still follows the normal
inspection path: detect a direct command when possible, or plan a specific natural-language request
after ambiguity checks; then validate the proposal and render the preview. It stops there: dry run
does not show a confirmation prompt and never executes the command.

Use dry run when you want to verify detection, planning, validation, policy outcome, and the final
rendered command before deciding whether to run the request normally. Direct commands that can be
detected locally skip Ollama planning, so a command like `poetry run oterminus --dry-run "ls"` does
not require a live Ollama service. Ambiguous natural-language requests stop before planning.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`dry-run <request>` instead.

### Explain mode

```bash
poetry run oterminus --explain "show running processes"
```

Explain mode is for learning and debugging why OTerminus chose a command. Like dry run, it performs
direct-command detection or natural-language planning, validation, and preview, then skips the
confirmation prompt and execution. It additionally renders reasoning about the selected command,
available flag or argument meanings, risk level, and policy interpretation, including blocked-policy
rationale when validation or policy rejects a proposal.

Use explain mode when you want to understand the path from request to command rather than simply
check the final preview. Direct commands that can be detected locally skip Ollama planning, so a
command like `poetry run oterminus --explain "ls"` does not require a live Ollama service. Ambiguous
natural-language requests stop before planning.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`explain <request>` or `explain <history_id>` instead.

`--dry-run` and `--explain` are mutually exclusive and apply to requests, not to the `doctor`
diagnostics command. For example, `poetry run oterminus --dry-run doctor` and
`poetry run oterminus doctor --dry-run` are invalid combinations.

## Autocomplete

Tab completion is available only in interactive REPL mode (`poetry run oterminus`) and is local
(`prompt_toolkit`) for:

- built-ins
- supported command families
- capability IDs (and optional capability hints)
- local filesystem paths

Autocomplete is deterministic and does not call Ollama.

If tab completion does not work:

```bash
poetry install
poetry run oterminus
```

If you use a globally installed or `pipx` build, rebuild/reinstall after dependency changes.

## Clear command

`clear` is supported and handled specially by the local executor using ANSI clear-screen output.

## Safety expectations

- OTerminus may block ambiguous broad/destructive natural-language requests before planning and
  suggest safer read-only inspections.
- Direct shell commands are not intercepted as ambiguous; they still go through validation and
  policy checks.
- Unsupported flags, operators, redirection/pipeline chains, and disallowed paths are rejected.
- Experimental mode is a constrained fallback and requires stronger confirmation.
- Commands that fail validation or policy checks are never executed.
