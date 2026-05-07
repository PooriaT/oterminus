# Routing and Planning

OTerminus separates deterministic intent routing from model-based planning. The `doctor` CLI mode is
outside this request-planning path: it runs diagnostics and exits before routing or planner setup.

## Deterministic router

`route_request()` classifies natural-language input using local hints and regex boundary matching.

Route categories:

- `filesystem_inspect`
- `filesystem_mutate`
- `text_search`
- `metadata_inspect`
- `process_inspect`
- `unsupported`

Router also suggests likely command families/capabilities from registry metadata.

## Direct command shortcut

If a one-shot or REPL request already looks like a supported command invocation, OTerminus builds a
direct proposal locally and skips Ollama planning. This shortcut also applies to `--dry-run` and
`--explain`; direct-command inspection modes can complete without a live Ollama service as long as
direct detection succeeds.

## Planner flow

Natural-language requests that are not direct commands use the planner. Planner calls Ollama with:

- a system prompt
- user prompt that includes request + route context + capability summaries

Planner parses model JSON into a strict `Proposal` schema. The model is asked to emit only
`structured` or `experimental` proposals and never executes commands itself.

## Structured-first normalization

Planner prefers structured mode when possible:

- if planner output already includes `command_family + arguments` for a structured family
- or if direct/planner command text can be parsed into a supported structured family

Structured mode remains the normal path for supported capabilities. Otherwise, the proposal stays
experimental: a constrained command-text fallback that is still allowlisted, validated, previewed,
and confirmed. Legacy `"mode": "raw"` input is parse-boundary compatibility only and is normalized
before downstream handling.

## Error handling

Planner errors include:

- invalid JSON from model
- schema mismatch
- invalid structured argument payloads

These become non-execution failures surfaced in CLI.
