# Observability

OTerminus provides local observability through audit events and optional verbose traces.

## Audit logging

When enabled, each request lifecycle writes one JSON line with fields covering:

- request metadata
- routing and proposal decisions
- validation outcome and reasons/warnings
- confirmation result
- execution exit code and timing

Audit configuration:

- `OTERMINUS_AUDIT_ENABLED`
- `OTERMINUS_AUDIT_LOG_PATH`
- `OTERMINUS_AUDIT_REDACT`

## Audit privacy

With redaction enabled (default), likely secret material is masked in command/request/reason fields and argv.

## Runtime diagnostics

- `--verbose` prints concise trace lines for routing/proposal/validation/confirmation
- `audit status` reports current audit settings and path
- `oterminus doctor` runs readiness and integrity checks

See [audit log schema reference](../reference/audit-log-schema.md).
