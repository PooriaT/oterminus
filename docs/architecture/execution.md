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

- `OTERMINUS_EXPLAIN_FAILURES` (default `false`): when enabled, OTerminus can generate a post-execution failure explanation for non-zero exit codes only.
- `OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS` (default `4000`): bounds redacted stderr/stdout snippets sent to the explainer and written to audit metadata.
- Suggested next actions are **never auto-executed**; they are displayed as dry-run/copy-only guidance.
- Output snippets are redacted and truncated; avoid sharing logs that may still contain sensitive paths or context.
