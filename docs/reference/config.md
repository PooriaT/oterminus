# Configuration Reference

OTerminus reads a small set of runtime settings from exported environment variables, a local `.env`
file, and a user config JSON file. The implementation in `src/oterminus/config.py` is the source of
truth for supported keys.

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
| Failure explanations enabled | `OTERMINUS_EXPLAIN_FAILURES` | Not supported | `false` | Opt-in local Ollama failure explanations for non-zero exits only. Suggested next actions are never executed automatically. |
| Failure explanation max chars | `OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS` | Not supported | `4000` | Positive integer. Bounds each redacted stdout/stderr snippet sent to the configured local Ollama model. |
| Command-pack profile preset | `OTERMINUS_COMMAND_PROFILE` | Not supported | Unset | Optional preset for command-pack availability (`beginner`, `safe`, `developer`, `power`). Unset preserves existing behavior. |
| Safe auto-execute | `OTERMINUS_AUTO_EXECUTE_SAFE` | Not supported | `false` | Environment-only opt-in. Uses the standard boolean parser. Only validated, warning-free, local read-only structured proposals from direct detection or the deterministic local planner may skip confirmation. |

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
- `OTERMINUS_EXPLAIN_FAILURES`
- `OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS`
- `OTERMINUS_COMMAND_PROFILE`
- `OTERMINUS_AUTO_EXECUTE_SAFE`

`OTERMINUS_MODEL` is not currently implemented. Set the persisted `model` field in the user config
file, or let first-run setup write it after you choose from installed Ollama models.

## Local `.env`

When OTerminus starts, it reads `OTERMINUS_*` keys from a `.env` file in the current working
directory. Exported shell environment variables take precedence over `.env` values.

Supported `.env` syntax is intentionally small:

```dotenv
OTERMINUS_AUTO_EXECUTE_SAFE=true
export OTERMINUS_AUDIT_REDACT=true
OTERMINUS_HISTORY_PATH="~/.oterminus/history.jsonl"
```

Blank lines and `#` comments are ignored. Values may be unquoted, single-quoted, or double-quoted.
There is no variable interpolation.

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

1. Exported environment variables are used first for settings that support an environment variable.
2. Local `.env` values are used next for `OTERMINUS_*` environment settings.
3. The user config file is used for persisted settings that support a JSON field.
4. Built-in defaults are used when none of the above provides a usable value.

In practice:

- `audit_log_path` follows full precedence: `OTERMINUS_AUDIT_LOG_PATH`, then user config
  `audit_log_path`, then `~/.oterminus/audit.jsonl`.
- `model` is user-config only; there is no environment override.
- timeout, policy, allowed roots, audit enabled/redaction, history settings, failure-explanation
  settings, safe auto-execute, and output limits are environment-only and fall back directly to
  defaults.
- malformed, missing, unreadable, or non-object user config JSON is ignored and defaults are used
  where applicable.

Audit management commands (`audit status`, `audit tail [n]`, and `audit clear`) read this active
configuration. If `OTERMINUS_AUDIT_ENABLED=false`, tail/clear report disabled state and do not
create a log file.

## Diagnostics visibility

`oterminus doctor` reports the current configuration and readiness state that affects startup,
including whether the configured model is available and whether the config, audit, and persistent
history paths are usable. If persistent history is disabled, doctor reports that state and does not
create or write a history file. It does not introduce additional configuration keys or environment
variables.

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
export OTERMINUS_AUTO_EXECUTE_SAFE=false
export OTERMINUS_EXPLAIN_FAILURES=false
export OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS=4000
```

## Command pack availability
Command-pack controls are config-only availability presets and filters. They **do not** bypass validator, policy mode, or confirmation.

### `OTERMINUS_COMMAND_PROFILE` (preset)
Set `OTERMINUS_COMMAND_PROFILE` to one of:

- `beginner`
- `safe`
- `developer`
- `power`

When unset, OTerminus keeps its prior behavior (no profile-based pack disablement).

Profile semantics are defined by disabled pack IDs:

- `beginner`: disables `archive`, `dangerous`, `git`, `macos`, `network`, `process`, `project`
- `safe`: disables `dangerous`, `network`, `project`
- `developer`: disables `dangerous`, `network`
- `power`: disables `dangerous`

### `OTERMINUS_DISABLED_COMMAND_PACKS` (explicit disable list)
Set `OTERMINUS_DISABLED_COMMAND_PACKS` to a comma-separated list of pack IDs (for example, `dangerous` or `process,macos`). Pack IDs are case-insensitive and validated.

Precedence rule:

1. Resolve profile disabled packs (if `OTERMINUS_COMMAND_PROFILE` is set).
2. Apply `OTERMINUS_DISABLED_COMMAND_PACKS` as additional disabled packs.

This means explicit disabled packs always disable additional packs and never re-enable profile-disabled packs.

All disabled packs are removed from planner, route, completion, and REPL discovery context. The validator remains authoritative: disabled commands are rejected before execution even if a user types a direct command or a planner proposes one. This is separate from capability IDs and does not change policy mode or confirmation.

## Safe auto-execute (opt-in)

`OTERMINUS_AUTO_EXECUTE_SAFE=false` by default. When explicitly set to `true`, OTerminus may skip
the interactive confirmation prompt only for a validated structured command that satisfies every
safe auto-execute rule.

```bash
export OTERMINUS_AUTO_EXECUTE_SAFE=true
```

The preview is still printed first, and validator/policy checks still run. Eligible proposals must
come from direct-command detection or the deterministic local planner, must be accepted with exact
`safe` risk, must have no warnings or rejection reasons, must resolve to an enabled and
platform-supported normally executable command spec, and must be local-only. Network-touching
commands, write or dangerous commands, experimental proposals, Ollama-planned proposals,
project-health commands, archive extraction or creation, history reruns, dry-run, and explain mode
never qualify.

When confirmation is skipped, audit records use
`confirmation_result: "skipped_auto_execute_safe"` and include bounded auto-execute decision fields.

## Command pack examples

```bash
# Restrictive starter preset.
export OTERMINUS_COMMAND_PROFILE=beginner

# Practical developer preset.
export OTERMINUS_COMMAND_PROFILE=developer

# Broad non-dangerous preset.
export OTERMINUS_COMMAND_PROFILE=power

# Start from developer preset, then additionally disable macos.
# Final disabled packs: dangerous, network, macos.
export OTERMINUS_COMMAND_PROFILE=developer
export OTERMINUS_DISABLED_COMMAND_PACKS=macos
```


## Privacy notes

Audit logs and persistent history are local JSONL files and are not uploaded by OTerminus. Audit
redaction is enabled by default, persistent history is disabled by default, and history redaction
defaults to audit redaction when unset. Audit and history records do not include full stdout/stderr,
but they can still contain local paths, command context, risk decisions, validation reasons, and
other sensitive operational context. Review these files before pasting them into issues, chats, or
public logs. Disable audit logging with `OTERMINUS_AUDIT_ENABLED=false`, keep persistent history
off with `OTERMINUS_HISTORY_ENABLED=false`, and keep failure explanations off with
`OTERMINUS_EXPLAIN_FAILURES=false`.

The curated `env` command is constrained to a single variable lookup (`env PATH`, not bare `env`)
and still warns because environment variables can contain secrets. Avoid querying secret-like
variables unless you intend to display them locally.

## Failure explanations (opt-in)

- `OTERMINUS_EXPLAIN_FAILURES` (default `false`): when enabled, OTerminus can generate a post-execution failure explanation for non-zero exit codes only.
- `OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS` (default `4000`): bounds redacted stderr/stdout snippets sent to the configured local Ollama explainer. Audit metadata stores the model-returned redacted summary, not full command output.
- Suggested next actions are **never auto-executed**; they are displayed as dry-run/copy-only guidance.
- Output snippets are redacted and truncated; avoid sharing logs that may still contain sensitive paths or context.
