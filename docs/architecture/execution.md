# Execution

Execution only happens after successful validation and explicit user confirmation.

## Executor behavior

The executor:

- runs argv with `subprocess.run` (no shell=True)
- captures stdout/stderr
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

Execution output is printed in a deterministic block (`--- execution output ---`) except for `clear` special handling.
