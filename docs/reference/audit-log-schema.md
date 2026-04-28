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
- `confirmation_result` (nullable string)
- `execution_exit_code` (nullable int)
- `rerun_source_history_id` (nullable int)
- `duration_ms` (nullable int)

## Redaction

When audit redaction is enabled, text and argv fields are passed through redaction helpers before writing.

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
