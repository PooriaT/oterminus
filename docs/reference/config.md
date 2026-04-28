# Configuration Reference

## Environment variables

- `OTERMINUS_TIMEOUT_SECONDS` (default `60`)
- `OTERMINUS_POLICY_MODE` (`safe` | `write` | `dangerous`, default `write`)
- `OTERMINUS_ALLOW_DANGEROUS` (`true`/`false`, default `false`)
- `OTERMINUS_ALLOWED_ROOTS` (colon-separated absolute roots)
- `OTERMINUS_CONFIG_PATH` (override user config file path)
- `OTERMINUS_AUDIT_LOG_PATH` (override audit JSONL path)
- `OTERMINUS_AUDIT_ENABLED` (`true`/`false`, default `true`)
- `OTERMINUS_AUDIT_REDACT` (`true`/`false`, default `true`)

## User config file

Default path:

- `~/.oterminus/config.json`

Supported persistent fields:

- `model` (selected Ollama model)
- `audit_log_path` (optional persisted audit path)

## Precedence behavior

- environment variables override defaults
- model and optional audit path can come from user config
- invalid/missing user config falls back safely to defaults

## Example

```bash
export OTERMINUS_POLICY_MODE=write
export OTERMINUS_ALLOW_DANGEROUS=false
export OTERMINUS_ALLOWED_ROOTS=/workspace:/tmp/safe-area
export OTERMINUS_AUDIT_ENABLED=true
export OTERMINUS_AUDIT_REDACT=true
```
