# Audit Log Schema

Audit logs are newline-delimited JSON objects (JSONL), one event per handled request.

## Default path

- `~/.oterminus/audit.jsonl` (overridable)

## Event fields

- `timestamp` (ISO8601 UTC)
- `user_input`
- `direct_command_detected` (bool)
- `ambiguity_detected` (bool)
- `ambiguity_reason` (nullable string)
- `ambiguity_safe_options` (string array)
- `routed_category` (nullable string)
- `proposal_mode` (nullable string)
- `command_family` (nullable string)
- `rendered_command` (nullable string)
- `argv` (string array)
- `validation_accepted` (nullable bool)
- `warnings` (string array)
- `rejection_reasons` (string array)
- `confirmation_result` (nullable string; includes statuses such as `confirmed`, `cancelled`,
  `skipped_dry_run`, `skipped_explain`, `not_prompted_rejected`, and `blocked_ambiguous`)
- `execution_exit_code` (nullable int)
- `stdout_truncated` (bool)
- `stderr_truncated` (bool)
- `stdout_original_chars` (nullable int)
- `stderr_original_chars` (nullable int)
- `stdout_visible_chars` (nullable int)
- `stderr_visible_chars` (nullable int)
- `rerun_source_history_id` (nullable int)
- `duration_ms` (nullable int)

## Ambiguity outcomes

Natural-language ambiguity detection runs after direct-command detection and before planner setup.
When an ambiguous request is blocked, the event records:

- `ambiguity_detected: true`
- `ambiguity_reason` with the matched phrase or broad-scope reason
- `ambiguity_safe_options` with read-only inspection alternatives
- `confirmation_result: "blocked_ambiguous"`

Planner, validator, confirmation, and executor fields remain unset because the request stops before
those stages.

## Rerun lineage

When a REPL user invokes `rerun <history_id>`, OTerminus reprocesses the original input as a new
request event. The new event sets `rerun_source_history_id` to the source history entry ID. Normal
validation/policy/confirmation rules still apply.

## Redaction

When audit redaction is enabled, text and argv fields are passed through redaction helpers before
writing. Audit events intentionally do not include raw stdout/stderr command output.

## User-facing audit commands

- `audit status`: reports enabled/disabled state, configured path, file existence, and redaction.
- `audit tail [n]`: shows most recent events from the local JSONL file (default `n=10`).
- `audit clear`: asks for exact confirmation (`CLEAR AUDIT`) before clearing the local log.

When audit is disabled, tail and clear commands do not create a new log file.

## Example (illustrative)

```json
{
  "timestamp": "2026-04-28T12:00:00+00:00",
  "user_input": "show disk space",
  "direct_command_detected": false,
  "routed_category": "metadata_inspect",
  "proposal_mode": "structured",
  "command_family": "df",
  "rendered_command": "df -h",
  "argv": ["df", "-h"],
  "validation_accepted": true,
  "warnings": [],
  "rejection_reasons": [],
  "confirmation_result": "confirmed",
  "execution_exit_code": 0,
  "duration_ms": 73
}
```

Note: persistent REPL history uses a separate local JSONL file (`OTERMINUS_HISTORY_PATH`) and is not an audit log replacement; reruns from persisted history still emit normal audit events.

## Failure explanations (opt-in)

When enabled, audit events may include:
- `failure_explanation_requested`
- `failure_explanation_generated`
- `failure_explanation_error`
- `failure_suggested_next_action` (redacted/bounded)
- `failure_stderr_summary` (redacted/bounded)

See [Configuration reference](config.md#failure-explanations-opt-in) for enablement and limits.

