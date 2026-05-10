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

## Redaction

When audit redaction is enabled, text and argv fields are passed through redaction helpers before
writing.

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
