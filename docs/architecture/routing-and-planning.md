# Routing and Planning

OTerminus separates deterministic intent routing from model-based planning.

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

## Planner flow

Planner calls Ollama with:

- a system prompt
- user prompt that includes request + route context + capability summaries

Planner parses model JSON into a strict `Proposal` schema.

## Structured-first normalization

Planner prefers structured mode when possible:

- if planner output already includes `command_family + arguments` for a structured family
- or if raw command text can be parsed into a supported structured family

Otherwise, proposal stays experimental.

## Error handling

Planner errors include:

- invalid JSON from model
- schema mismatch
- invalid structured argument payloads

These become non-execution failures surfaced in CLI.
