# Configuration Reference

OTerminus reads a small set of runtime settings from environment variables and a user config JSON
file. The implementation in `src/oterminus/config.py` is the source of truth for supported keys.

## Supported settings

| Setting | Environment variable | User config field | Default | Notes |
| --- | --- | --- | --- | --- |
| Execution timeout | `OTERMINUS_TIMEOUT_SECONDS` | Not supported | `60` | Parsed as an integer number of seconds and passed to the executor. |
| Max execution output chars | `OTERMINUS_MAX_OUTPUT_CHARS` | Not supported | `20000` | Positive integer. Values `<1` or invalid values fall back to `20000`. Applied independently to stdout and stderr after command completion. |
| Policy mode | `OTERMINUS_POLICY_MODE` | Not supported | `write` | Must be one of `safe`, `write`, or `dangerous`. |
| Dangerous-operation gate | `OTERMINUS_ALLOW_DANGEROUS` | Not supported | `false` | Only the exact value `true` enables dangerous operations, and only when policy mode is `dangerous`. |
| Allowed path roots | `OTERMINUS_ALLOWED_ROOTS` | Not supported | Empty list | Colon-separated roots. When set, path operands must resolve under one of these roots. |
| User config path | `OTERMINUS_CONFIG_PATH` | Environment-only | `~/.oterminus/config.json` | Selects which JSON config file is loaded and saved. |
| Selected Ollama model | Not supported | `model` | None | Saved during first-run setup. There is currently no supported `OTERMINUS_MODEL` environment override. |
| Audit log path | `OTERMINUS_AUDIT_LOG_PATH` | `audit_log_path` | `~/.oterminus/audit.jsonl` | Environment value overrides the user config field. |
| Audit enabled | `OTERMINUS_AUDIT_ENABLED` | Not supported | `true` | Accepts `1`, `true`, `yes`, or `on` as true; `0`, `false`, `no`, or `off` as false. Invalid values keep the default. |
| Audit redaction | `OTERMINUS_AUDIT_REDACT` | Not supported | `true` | Uses the same boolean parsing as `OTERMINUS_AUDIT_ENABLED`. |
| Persistent history enabled | `OTERMINUS_HISTORY_ENABLED` | Not supported | `false` | Enables local JSONL history persistence for REPL entries. When false, history is session-only. |
| Persistent history path | `OTERMINUS_HISTORY_PATH` | Not supported | `~/.oterminus/history.jsonl` | Local JSONL file used when persistent history is enabled. |
| Persistent history limit | `OTERMINUS_HISTORY_LIMIT` | Not supported | `100` | Maximum number of persisted records loaded into each REPL session. Must be a valid integer in the environment; loaded values are clamped to at least `1` by the history store. |
| Persistent history redaction | `OTERMINUS_HISTORY_REDACT` | Not supported | Follows `OTERMINUS_AUDIT_REDACT` | Uses the same boolean parsing as `OTERMINUS_AUDIT_ENABLED`; controls redaction before writing history records. |

## Environment variables

Supported `OTERMINUS_*` variables are:

- `OTERMINUS_TIMEOUT_SECONDS`
- `OTERMINUS_MAX_OUTPUT_CHARS`
- `OTERMINUS_POLICY_MODE`
- `OTERMINUS_ALLOW_DANGEROUS`
- `OTERMINUS_ALLOWED_ROOTS`
- `OTERMINUS_CONFIG_PATH`
- `OTERMINUS_AUDIT_LOG_PATH`
- `OTERMINUS_AUDIT_ENABLED`
- `OTERMINUS_AUDIT_REDACT`
- `OTERMINUS_HISTORY_ENABLED`
- `OTERMINUS_HISTORY_PATH`
- `OTERMINUS_HISTORY_LIMIT`
- `OTERMINUS_HISTORY_REDACT`

`OTERMINUS_MODEL` is not currently implemented. Set the persisted `model` field in the user config
file, or let first-run setup write it after you choose from installed Ollama models.

## User config file

Default path:

- `~/.oterminus/config.json`

Set `OTERMINUS_CONFIG_PATH` to read and write a different config JSON file.

Supported persistent fields:

```json
{
  "model": "gemma4",
  "audit_log_path": "~/.oterminus/audit.jsonl"
}
```

The `model` field is the selected local Ollama model. The `audit_log_path` field is optional and is
used only when `OTERMINUS_AUDIT_LOG_PATH` is unset.

## Precedence behavior

Precedence depends on the setting:

1. Environment variables are used first for settings that support an environment variable.
2. The user config file is used for persisted settings that support a JSON field.
3. Built-in defaults are used when neither of the above provides a usable value.

In practice:

- `audit_log_path` follows full precedence: `OTERMINUS_AUDIT_LOG_PATH`, then user config
  `audit_log_path`, then `~/.oterminus/audit.jsonl`.
- `model` is user-config only; there is no environment override.
- timeout, policy, allowed roots, audit enabled/redaction, and all history settings are
  environment-only and fall back directly to defaults.
- malformed, missing, unreadable, or non-object user config JSON is ignored and defaults are used
  where applicable.

Audit management commands (`audit status`, `audit tail [n]`, and `audit clear`) read this active
configuration. If `OTERMINUS_AUDIT_ENABLED=false`, tail/clear report disabled state and do not
create a log file.

## Diagnostics visibility

`poetry run oterminus doctor` reports the current configuration and readiness state that affects
startup, including whether the configured model is available and whether the audit path is usable.
It does not introduce additional configuration keys or environment variables.

## Example

```bash
export OTERMINUS_POLICY_MODE=write
export OTERMINUS_ALLOW_DANGEROUS=false
export OTERMINUS_ALLOWED_ROOTS=/workspace:/tmp/safe-area
export OTERMINUS_AUDIT_LOG_PATH=~/.oterminus/audit.jsonl
export OTERMINUS_AUDIT_ENABLED=true
export OTERMINUS_AUDIT_REDACT=true
export OTERMINUS_HISTORY_ENABLED=false
export OTERMINUS_HISTORY_PATH=~/.oterminus/history.jsonl
export OTERMINUS_HISTORY_LIMIT=100
export OTERMINUS_HISTORY_REDACT=true
```

## Command pack availability
Set `OTERMINUS_DISABLED_COMMAND_PACKS` to a comma-separated list of pack IDs (e.g. `dangerous`, `process,macos`). Pack IDs are case-insensitive and validated. Disabled packs are removed from planner/completion context and commands are rejected by validator before execution. This is separate from capability IDs and does not change policy mode.


## Failure explanations (opt-in)

- `OTERMINUS_EXPLAIN_FAILURES` (default `false`): when enabled, OTerminus can generate a post-execution failure explanation for non-zero exit codes only.
- `OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS` (default `4000`): bounds redacted stderr/stdout snippets sent to the explainer and written to audit metadata.
- Suggested next actions are **never auto-executed**; they are displayed as dry-run/copy-only guidance.
- Output snippets are redacted and truncated; avoid sharing logs that may still contain sensitive paths or context.
