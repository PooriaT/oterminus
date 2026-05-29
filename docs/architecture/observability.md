# Observability

OTerminus provides local observability through audit events, optional persistent history, opt-in failure explanations, and optional verbose traces. These artifacts stay local; OTerminus does not upload audit logs or history.

## Audit logging

When enabled, each request lifecycle writes one JSON line with fields covering:

- request metadata
- ambiguity outcome for blocked natural-language requests
- planner fast-path diagnostics (`planner_invoked`, `planner_skipped`, `planner_skip_reason`)
- routing and proposal decisions when planning continues
- validation outcome and reasons/warnings
- confirmation result or lifecycle stop status
- execution exit code and timing
- stage-level latency metrics (`timings_ms`) to show where time was spent and whether planner was skipped
- execution output truncation metadata (flags and character counts), without storing raw stdout/stderr
- rerun lineage (`rerun_source_history_id`) when a request is triggered via `rerun <history_id>`

For ambiguous natural-language requests, the audit event records `ambiguity_detected`,
`ambiguity_reason`, `ambiguity_safe_options`, `confirmation_result: "blocked_ambiguous"`, and
`planner_skip_reason: "ambiguity_blocked"`.
Because the request stops before planning, validation, confirmation, and execution, the downstream
fields for those stages remain unset.

Audit configuration:

- `OTERMINUS_AUDIT_ENABLED`
- `OTERMINUS_AUDIT_LOG_PATH`
- `OTERMINUS_AUDIT_REDACT`

## Audit privacy

With redaction enabled (default), likely secret material is masked in command/request/reason fields
and argv before JSONL writes. Audit events store stdout/stderr truncation metadata (for example original/visible character counts and truncation flags), not full command output. Redaction is best-effort, and logs may still include local paths, command context, and validation decisions, so users should review them before sharing.

## Runtime diagnostics

- `--verbose` prints concise trace lines for fast-path/planner decisions, routing, proposal,
  validation, and confirmation (for example: `fast_path=direct_command planner=skipped` and
  `planner=invoked`)
- `audit status` reports current audit settings and path
- `audit tail [n]` prints recent local audit events without executing a request
- `audit clear` requires explicit confirmation before clearing the local audit log
- `oterminus doctor` runs readiness and integrity checks, including whether configured audit and
  persistent-history directories are usable

See [audit log schema reference](../reference/audit-log-schema.md).

Persistent REPL history is optional and local-only (JSONL). It stores request/decision metadata (not stdout/stderr) and may be redacted before write.

## Persistent history privacy

Persistent REPL history is separate from audit logging and is disabled by default. When enabled (`OTERMINUS_HISTORY_ENABLED=true`), records are stored only on the local machine as JSONL at `OTERMINUS_HISTORY_PATH`. It can be disabled again with `OTERMINUS_HISTORY_ENABLED=false`.

Persisted history records may include request text, rendered command text, local paths, routing/proposal metadata, risk and validation status, execution status, and rerun lineage IDs. They do not store command stdout/stderr, full failure output, or raw planner responses.

`OTERMINUS_HISTORY_REDACT` defaults to the audit-redaction setting and can redact obvious secret-looking values before write, but redaction is best-effort and does not guarantee removal of all sensitive context. Review history content before copying, pasting, or publishing it.

## Failure explanations (opt-in)

Failure explanations are disabled by default (`OTERMINUS_EXPLAIN_FAILURES=false`). When enabled, OTerminus sends only redacted and truncated command/stdout/stderr snippets to the configured local Ollama model, never full audit logs or history. Suggested next actions are rendered as guidance and are not executed automatically. Audit captures only bounded metadata for failure explanation outcomes (not full stdout/stderr).
See [Audit log schema](../reference/audit-log-schema.md) and [Configuration reference](../reference/config.md#failure-explanations-opt-in).

## Environment output privacy

Environment variables often contain credentials. Curated `env` support is constrained to single-variable lookups and validation emits a warning even for accepted lookups. Bare `env` and multi-variable dumps are rejected in curated mode, and users should avoid sharing env output publicly without review.

- `planner_skip_reason` now includes `local_planner` when deterministic local planning produced the proposal.
- Verbose trace includes `fast_path=local_planner` with a rule id on matches, and `local_planner=no_match planner=invoked` on misses.
