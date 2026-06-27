# Configuration Reference

OTerminus reads a small set of runtime settings from exported environment variables, a local `.env`
file, and a user config JSON file. The implementation in `src/oterminus/config.py` is the source of
truth for supported keys.

## Supported settings

| Setting | Environment variable | User config field | Default | Notes |
| --- | --- | --- | --- | --- |
| Execution timeout | `OTERMINUS_TIMEOUT_SECONDS` | `timeout_seconds` | `60` | Positive integer number of seconds passed to the executor. |
| Max execution output chars | `OTERMINUS_MAX_OUTPUT_CHARS` | `max_output_chars` | `20000` | Positive integer. Invalid env values fall back to `20000`. Applied independently to stdout and stderr after command completion. |
| Terminal color mode | `OTERMINUS_COLOR` | `color_mode` | `auto` | Must be `auto`, `always`, or `never`. Invalid env values fall back to `auto`; invalid persisted values are config errors. `NO_COLOR` disables ANSI styling at render time even when this is `always`. |
| Policy mode | `OTERMINUS_POLICY_MODE` | `policy_mode` | `write` | Must be one of `safe`, `write`, or `dangerous`. |
| Dangerous-operation gate | `OTERMINUS_ALLOW_DANGEROUS` | Not supported | `false` | Environment/.env only. It is never persisted and only matters when policy mode is `dangerous`. |
| Allowed path roots | `OTERMINUS_ALLOWED_ROOTS` | `allowed_roots` | Empty list | Environment form is colon-separated. JSON form is a list of path strings. When set, path operands must resolve under one of these roots. |
| User config path | `OTERMINUS_CONFIG_PATH` | Environment/.env only | `~/.oterminus/config.json` | Selects which JSON config file is loaded and saved. It cannot be read from the file whose path it selects. |
| Selected Ollama model | Not supported | `model` | None | Saved during first-run setup. There is currently no supported `OTERMINUS_MODEL` environment override. |
| Audit log path | `OTERMINUS_AUDIT_LOG_PATH` | `audit_log_path` | `~/.oterminus/audit.jsonl` | Environment value overrides the user config field. |
| Audit enabled | `OTERMINUS_AUDIT_ENABLED` | `audit_enabled` | `true` | Accepts `1`, `true`, `yes`, or `on` as true; `0`, `false`, `no`, or `off` as false. Invalid env values keep the default. |
| Audit redaction | `OTERMINUS_AUDIT_REDACT` | `audit_redact` | `true` | Uses the same boolean parsing as `OTERMINUS_AUDIT_ENABLED`. |
| Persistent history enabled | `OTERMINUS_HISTORY_ENABLED` | `history_enabled` | `false` | Enables local JSONL history persistence for REPL entries. When false, history is session-only. |
| Persistent history path | `OTERMINUS_HISTORY_PATH` | `history_path` | `~/.oterminus/history.jsonl` | Local JSONL file used when persistent history is enabled. |
| Persistent history limit | `OTERMINUS_HISTORY_LIMIT` | `history_limit` | `100` | Maximum number of persisted records loaded into each REPL session. |
| Persistent history redaction | `OTERMINUS_HISTORY_REDACT` | `history_redact` | Follows effective audit redaction | Controls redaction before writing history records. When unset everywhere, it follows the effective audit-redaction setting. |
| Failure explanations enabled | `OTERMINUS_EXPLAIN_FAILURES` | `explain_failures` | `false` | Opt-in local Ollama failure explanations for non-zero exits only. Suggested next actions are never executed automatically. |
| Failure explanation max chars | `OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS` | `failure_explanation_max_chars` | `4000` | Positive integer. Bounds each redacted stdout/stderr snippet sent to the configured local Ollama model. |
| Command-pack profile preset | `OTERMINUS_COMMAND_PROFILE` | `command_profile` | Unset | Optional preset for command-pack availability (`beginner`, `safe`, `developer`, `power`). Unset preserves existing behavior. |
| Explicit disabled command packs | `OTERMINUS_DISABLED_COMMAND_PACKS` | `disabled_command_packs` | Empty list | Environment form is comma-separated. JSON form is a list of pack IDs. Explicit packs are unioned with profile-disabled packs. |
| Deterministic shortcuts | `OTERMINUS_DETERMINISTIC_SHORTCUTS` | `deterministic_shortcuts` | `minimal` | Must be `off` or `minimal`. Controls the optional shortcut layer between routing metadata and the LLM planner. There is no broad/full mode. |
| Safe auto-execute | `OTERMINUS_AUTO_EXECUTE_SAFE` | `auto_execute_safe` | `false` | Uses the standard boolean parser. Only validated, warning-free, local read-only structured proposals from direct detection or deterministic shortcuts may skip confirmation. |
| Schema version | Not supported | `schema_version` | `1` | Current persistent user-config schema version. Missing legacy files are normalized in memory as version 1. |
| Onboarding state | Not supported | `onboarding_completed` | `false` | Reserved for first-run onboarding. Existing legacy config files without a schema version are treated as completed in memory. |

## Environment variables

Supported `OTERMINUS_*` variables are:

- `OTERMINUS_TIMEOUT_SECONDS`
- `OTERMINUS_MAX_OUTPUT_CHARS`
- `OTERMINUS_COLOR`
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
- `OTERMINUS_DETERMINISTIC_SHORTCUTS`
- `OTERMINUS_AUTO_EXECUTE_SAFE`

`OTERMINUS_MODEL` is not currently implemented. Use `oterminus config set model <name>` to persist
the model, or let first-run setup write it after you choose from installed Ollama models.

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
  "schema_version": 1,
  "onboarding_completed": false,
  "model": "gemma4",
  "command_profile": "developer",
  "deterministic_shortcuts": "minimal",
  "disabled_command_packs": ["macos"],
  "policy_mode": "write",
  "allowed_roots": ["/workspace"],
  "auto_execute_safe": false,
  "timeout_seconds": 60,
  "max_output_chars": 20000,
  "color_mode": "auto",
  "audit_enabled": true,
  "audit_redact": true,
  "audit_log_path": "~/.oterminus/audit.jsonl",
  "history_enabled": false,
  "history_path": "~/.oterminus/history.jsonl",
  "history_limit": 100,
  "history_redact": true,
  "explain_failures": false,
  "failure_explanation_max_chars": 4000
}
```

The user config is validated with a versioned schema. Unknown fields, malformed JSON, non-object
JSON, unsupported future schema versions, invalid enum values, non-boolean booleans, blank model
names, invalid pack IDs, and non-positive integer values are configuration errors. OTerminus reports
a concise error and exits non-zero instead of silently discarding the bad value.

Existing legacy files such as `{"model": "gemma4"}` or
`{"model": "gemma4", "audit_log_path": "~/.oterminus/audit.jsonl"}` remain supported. When a file
exists without `schema_version`, OTerminus normalizes it in memory as schema version 1 and treats
`onboarding_completed` as true unless the file explicitly contains a supported value. Missing config
files are different: they have no completion state and use runtime defaults.

The config file is local preference storage, not secret storage. Do not put tokens, passwords, or
other secrets in it.

## Config commands

Use `oterminus config` for configuration management. This namespace is intentionally not
`oterminus --config`; the flag shape is reserved for a possible future alternate-config-path option.
All config commands bypass the normal request lifecycle and do not require Ollama.

| Command | Behavior |
| --- | --- |
| `oterminus config` | Prints concise help for config subcommands and exits successfully. |
| `oterminus config path` | Prints only the active config path. Respects exported `OTERMINUS_CONFIG_PATH` and current-directory `.env`; does not create the file. |
| `oterminus config show` | Shows the active path, existence, schema version when valid, effective settings, and per-setting source (`environment`, `.env`, `user config`, `default`, or `derived`). |
| `oterminus config get <key>` | Prints one supported effective setting as `key=value`. Uses the same precedence as `config show`; output is one plain line with no ANSI styling. |
| `oterminus config set <key> <value>` | Updates one supported safe setting in the user config JSON. Validates through the user-config schema, preserves unrelated fields, writes atomically, and prints the target path. |
| `oterminus config reset <key>` | Removes one supported safe setting from the user config JSON so effective resolution falls back to environment, `.env`, then default. Preserves unrelated fields and does not create a missing file. |
| `oterminus config reset --all-safe` | Removes all supported safe user-facing settings from the user config JSON. Preserves paths, lists, policy mode, schema version, onboarding state, and other advanced fields. |
| `oterminus config init` | Runs the interactive onboarding wizard when stdin is a TTY. Existing valid config values are used as defaults and only wizard-managed fields are revised after summary confirmation. |
| `oterminus config init --defaults` | Creates safe non-interactive defaults and prints the path. Existing files are not overwritten. Required for non-TTY initialization. |
| `oterminus config init --defaults --force` | Replaces an existing valid config with safe defaults. Invalid existing files are preserved and must be repaired or moved first. |
| `oterminus config validate` | Validates only the active persistent file. Missing, malformed, unsupported, unreadable, or schema-invalid files exit non-zero. |
| `oterminus config edit` | Opens the config with `$VISUAL`, then `$EDITOR`. If missing, safe defaults are created first. After a successful editor exit, the file is validated; invalid edits are preserved. |

Safe defaults mark onboarding completed, use the `safe` command profile, keep deterministic
shortcuts at `minimal`, keep policy mode at `write`, leave dangerous permission out of the file,
disable safe auto-execute, history, and failure explanations, and enable audit logging plus
redaction. `config edit` parses the editor with argv semantics, preserves arguments such as
`code --wait`, never uses `shell=True`, does not guess an editor, does not open a browser, and does
not modify shell startup files.

### Safe get/set/reset keys

`config get`, `config set`, and `config reset` intentionally support only a small allowlist:

- `model`
- `command_profile`
- `deterministic_shortcuts`
- `auto_execute_safe`
- `audit_enabled`
- `audit_redact`
- `history_enabled`
- `history_redact`
- `explain_failures`
- `color_mode`
- `timeout_seconds`
- `max_output_chars`

Unsupported fields include `allow_dangerous`, `policy.allow_dangerous`, `allowed_roots`,
`disabled_command_packs`, `policy.mode`, `audit_log_path`, `history_path`, `history_limit`,
`failure_explanation_max_chars`, `schema_version`, and `onboarding_completed`. List, path, policy,
schema, and onboarding fields are not casual CLI mutations. Dangerous execution remains
environment-only with `OTERMINUS_ALLOW_DANGEROUS`; it is never written to the user config and has no
hidden alias.

`config reset --all-safe` resets exactly the same supported safe set:

- `model`
- `command_profile`
- `deterministic_shortcuts`
- `auto_execute_safe`
- `audit_enabled`
- `audit_redact`
- `history_enabled`
- `history_redact`
- `explain_failures`
- `color_mode`
- `timeout_seconds`
- `max_output_chars`

It intentionally preserves `schema_version`, `onboarding_completed`, `allowed_roots`,
`disabled_command_packs`, `policy_mode`, `audit_log_path`, `history_path`, `history_limit`, and
`failure_explanation_max_chars`. It does not reset dangerous execution controls, delete the config
file, edit `.env`, modify shell startup files, or rewrite unrelated JSON fields.

`config get <key>` prints one line:

```text
color_mode=auto
auto_execute_safe=false
model=
```

Booleans are printed as `true` or `false`. Enums are printed as their values, such as
`color_mode=never` or `command_profile=safe`. When `model` or `command_profile` is unset, the value
is empty after the equals sign.

`config set <key> <value>` updates only the persistent user config file selected by
`OTERMINUS_CONFIG_PATH`, current-directory `.env`, or the default path. It does not edit exported
environment variables, `.env`, shell startup files, audit/history files, or arbitrary JSON fields.
If the config file is missing, OTerminus creates a minimal schema-versioned file containing the
changed value. If the existing file is invalid, the command refuses to overwrite it; run
`oterminus config validate`, repair the file, or move it aside.

Accepted `config set` values:

- `model`: any nonblank string after trimming surrounding whitespace. Use `none` or `null` to clear
  a persisted model.
- `command_profile`: `beginner`, `safe`, `developer`, or `power`, case-insensitive and persisted
  lowercase.
- `deterministic_shortcuts`: `off` or `minimal`, case-insensitive and persisted lowercase.
- Boolean keys: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`, case-insensitive and
  persisted as JSON booleans.
- `color_mode`: `auto`, `always`, or `never`, case-insensitive and persisted lowercase.
- `timeout_seconds` and `max_output_chars`: positive base-10 integers. Zero, negatives, floats, and
  non-integers are rejected before writing.

`config set` writes the user config only. If an exported environment variable or current-directory
`.env` still overrides that field, the command prints a note, for example:

```text
Updated auto_execute_safe=true in /home/me/.oterminus/config.json
Note: effective value is currently overridden by OTERMINUS_AUTO_EXECUTE_SAFE from environment.
```

`config reset <key>` also writes the user config only. When possible, it removes the persisted key
instead of writing a default value, so the effective value follows normal precedence:

1. exported environment
2. current-directory `.env`
3. default

For example, if the file contains `color_mode: never`, `oterminus config reset color_mode` removes
only `color_mode` and preserves unrelated fields such as `audit_enabled`, paths, allowed roots,
disabled packs, and onboarding state. If the config file is missing, reset reports that there is no
persisted value and does not create a file. If the existing file is invalid, reset refuses to
overwrite it and suggests `oterminus config validate`. If environment or `.env` still controls the
same setting after reset, the command prints a note naming that source.

To recover from an invalid config, run `oterminus config validate` for the field-level error, then
edit the file manually or with `VISUAL=... oterminus config edit`. If the file is not worth
repairing, move it aside and run `oterminus config init --defaults`.

## First-run onboarding

Automatic onboarding appears only for a bare interactive `oterminus` launch when stdin is a TTY and
the persistent config file does not exist. It does not appear for one-shot requests, `--dry-run`,
`--explain`, `doctor`, `version`, `completion`, any `config` command, existing config files, legacy
config files, or non-interactive stdin. One-shot direct commands are not gated by onboarding and can
still detect, validate, preview, confirm, and execute without Ollama.

Run the wizard later with:

```bash
oterminus config init
```

The wizard-managed fields and first-run defaults are:

| Field | Default | Notes |
| --- | --- | --- |
| `command_profile` | `safe` | Choose `beginner`, `safe`, `developer`, or `power`. The prompt describes disabled packs using the command registry/profile mapping. |
| `auto_execute_safe` | `false` | Applies only to narrowly eligible validated local read-only commands from direct detection or deterministic shortcuts. Network, write, dangerous, experimental, warning-bearing, LLM-planned, project-health, archive-mutation, and rerun requests do not qualify. |
| `audit_enabled` | `true` | Audit logs remain local and do not store full stdout/stderr, but may contain paths and command context. Review before sharing. |
| `audit_redact` | `true` | Kept safe even if audit logging is disabled. |
| `history_enabled` | `false` | Persisted history may include commands, local paths, and execution context. Reruns still require validation and confirmation. |
| `history_redact` | `true` | Kept safe even if persistent history is disabled. |
| `explain_failures` | `false` | When enabled, redacted/truncated command output may be sent to the configured local Ollama model after non-zero exits. Suggested next actions are never executed automatically. |
| `model` | Not configured | Optional. If Ollama is unavailable or no models are installed, onboarding saves non-model preferences and model setup can happen later. |

Before saving, onboarding prints a summary with the selected profile, auto-execute state, audit and
history settings, failure-explanation state, selected model or `not configured`, and target config
path. Declining the final summary does not write changes. When rerun against an existing valid
config, the wizard preserves unmanaged fields such as numeric limits, paths, allowed roots, policy
mode, and explicit disabled packs. On successful save it sets `onboarding_completed` to `true`.

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
  settings, safe auto-execute, deterministic shortcuts, command profiles, disabled packs, terminal color mode, and output limits follow
  environment, `.env`, user config, default precedence.
- `OTERMINUS_CONFIG_PATH` is environment/.env only.
- `OTERMINUS_ALLOW_DANGEROUS` is environment/.env only and is rejected if persisted.
- `NO_COLOR` is not a stored config value; when present in the render environment it disables ANSI
  styling after `color_mode` is resolved.
- `history_redact`, when absent from all sources, follows the effective audit-redaction setting.
- invalid persisted values are reported as configuration errors; missing config files simply use
  defaults.

## Terminal Styling

`color_mode` controls whether semantic terminal styling may emit ANSI escape sequences. The styling
layer is intentionally small and dependency-free; it does not add Rich or Colorama.

- `auto`: enable styling only for TTY output when `TERM` is not `dumb` and `NO_COLOR` is unset.
- `always`: enable styling even when stdout/stderr is redirected, unless `NO_COLOR` is set.
- `never`: never emit ANSI styling.

```bash
export OTERMINUS_COLOR=auto
export OTERMINUS_COLOR=always
export OTERMINUS_COLOR=never
NO_COLOR=1 oterminus
```

Colors are semantic and supplementary. OTerminus-owned previews, confirmation prompts, lifecycle
messages, doctor output, discovery/help output, and the REPL prompt may use color, but text labels
remain visible in every mode. When styling is disabled, the terminal style layer returns the exact
original text.

Shell completion scripts, version output, `config path`, JSON-oriented config output,
audit/history records, and subprocess stdout/stderr metadata remain plain. OTerminus does not
recolor command stdout/stderr, and serialized audit/history files do not contain ANSI escape
sequences.

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
export OTERMINUS_COLOR=auto
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

1. Resolve profile disabled packs from `OTERMINUS_COMMAND_PROFILE`, `.env`, or user config.
2. Resolve explicit disabled packs from `OTERMINUS_DISABLED_COMMAND_PACKS`, `.env`, or user config.
3. Union profile-disabled packs with explicit disabled packs.

When an explicit environment or `.env` disabled-pack list is present, it replaces the persisted
explicit list before the union is calculated. Explicit disabled packs always disable additional
packs and never re-enable profile-disabled packs.

All disabled packs are removed from planner, route, completion, and REPL discovery context. The validator remains authoritative: disabled commands are rejected before execution even if a user types a direct command or a planner proposes one. This is separate from capability IDs and does not change policy mode or confirmation.

## Safe auto-execute (opt-in)

`OTERMINUS_AUTO_EXECUTE_SAFE=false` by default. When explicitly set to `true`, OTerminus may skip
the interactive confirmation prompt only for a validated structured command that satisfies every
safe auto-execute rule.

```bash
export OTERMINUS_AUTO_EXECUTE_SAFE=true
```

The preview is still printed first, and validator/policy checks still run. Eligible proposals must
come from direct-command detection or deterministic shortcuts, must be accepted with exact
`safe` risk, must have no warnings or rejection reasons, must resolve to an enabled and
platform-supported normally executable command spec, and must be local-only. Network-touching
commands, write or dangerous commands, experimental proposals, LLM-planned proposals,
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
