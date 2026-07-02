# Execution

Execution only happens after successful validation and explicit user confirmation. Diagnostics and
inspection modes intentionally stop earlier: `doctor` is outside the execution lifecycle, while
`--dry-run`, `--explain`, and the REPL `dry-run`/`explain` built-ins skip confirmation and execution.

## Run-mode behavior

- Execute mode: validate, preview, ask for confirmation, then run only if confirmed.
- Dry-run mode: run direct detection or planning, validation, and preview, then stop without
  confirmation or execution.
- Explain mode: run direct detection or planning, validation, preview, and explanation rendering,
  then stop without confirmation or execution.

Direct-command dry-run/explain requests skip Ollama planning when direct detection succeeds.

## Executor behavior

The executor:

- runs argv with `subprocess.run` (no shell=True)
- captures stdout/stderr
- truncates captured stdout/stderr to `OTERMINUS_MAX_OUTPUT_CHARS` (default `20000`) after subprocess completion
- enforces timeout
- returns structured execution result

## Special built-ins

- `cd`: handled in-process so REPL working directory changes persist for session
- `clear`: handled via ANSI clear sequence output

## Error handling

CLI maps execution failures to user-visible statuses:

- timeout
- subprocess/system errors
- keyboard interruption
- non-zero command exit codes

Execution output is printed in a deterministic block (`--- execution output ---`) except for `clear`
special handling.


When truncation occurs, CLI output includes explicit notices for stdout/stderr truncation while preserving return code semantics. Dry-run/explain modes are unaffected because they do not execute commands.

## Failure explanations (opt-in)

Execution can optionally include a post-failure explanation after a non-zero exit.
See [Configuration reference](../reference/config.md#failure-explanations-opt-in) for settings and [User guide](../product/user-guide.md#failure-explanations-opt-in) for behavior and safety notes.

