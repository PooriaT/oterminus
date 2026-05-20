# Observability

OTerminus provides local observability through audit events and optional verbose traces.

## Audit logging

When enabled, each request lifecycle writes one JSON line with fields covering:

- request metadata
- ambiguity outcome for blocked natural-language requests
- routing and proposal decisions when planning continues
- validation outcome and reasons/warnings
- confirmation result or lifecycle stop status
- execution exit code and timing
- execution output truncation metadata (flags and character counts), without storing raw stdout/stderr
- rerun lineage (`rerun_source_history_id`) when a request is triggered via `rerun <history_id>`

For ambiguous natural-language requests, the audit event records `ambiguity_detected`,
`ambiguity_reason`, `ambiguity_safe_options`, and `confirmation_result: "blocked_ambiguous"`.
Because the request stops before planning, validation, confirmation, and execution, the downstream
fields for those stages remain unset.

Audit configuration:

- `OTERMINUS_AUDIT_ENABLED`
- `OTERMINUS_AUDIT_LOG_PATH`
- `OTERMINUS_AUDIT_REDACT`

## Audit privacy

With redaction enabled (default), likely secret material is masked in command/request/reason fields
and argv.

## Runtime diagnostics

- `--verbose` prints concise trace lines for routing/proposal/validation/confirmation
- `audit status` reports current audit settings and path
- `audit tail [n]` prints recent local audit events without executing a request
- `audit clear` requires explicit confirmation before clearing the local audit log
- `oterminus doctor` runs readiness and integrity checks

See [audit log schema reference](../reference/audit-log-schema.md).

Persistent REPL history is optional and local-only (JSONL). It stores request/decision metadata (not stdout/stderr) and may be redacted before write.

## Persistent history privacy

Persistent REPL history is separate from audit logging and is disabled by default. When enabled (`OTERMINUS_HISTORY_ENABLED=true`), records are stored only on the local machine as JSONL at `OTERMINUS_HISTORY_PATH`.

Persisted history records may include request text, rendered command text, local paths, routing/proposal metadata, risk and validation status, execution status, and rerun lineage IDs. They do not store command stdout/stderr.

`OTERMINUS_HISTORY_REDACT` can redact obvious secret-looking values before write, but redaction is best-effort and does not guarantee removal of all sensitive context. Review history content before copying, pasting, or publishing it.
