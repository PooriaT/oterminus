# Routing and Planning

OTerminus separates deterministic intent routing from model-based planning. The `doctor` CLI mode is
outside this request-planning path: it runs diagnostics and exits before routing or planner setup.
Before routing, OTerminus first checks for direct commands and then applies ambiguity detection to
non-direct natural-language requests.

## Lifecycle before routing

Routing is reached only after two earlier checks:

1. **Direct command detection**: supported direct shell commands skip the planner but still continue
   to validation and policy. They are not treated as ambiguous natural language.
2. **Ambiguity detection**: vague natural-language requests stop before routing and planner calls.
   These are logged as planner-skipped fast-path outcomes (`planner_skip_reason=ambiguity_blocked`).
   OTerminus shows safe read-only inspection alternatives and does not execute anything.

## Deterministic router

`route_request()` classifies specific natural-language input using local hints and regex boundary
matching.

Route categories:

- `filesystem_inspect`
- `filesystem_mutate`
- `text_search`
- `metadata_inspect`
- `process_inspect`
- `network_diagnostics`
- `unsupported`

Router also suggests likely command families/capabilities from registry metadata.

## Direct command shortcut

If a one-shot or REPL request already looks like a supported command invocation, OTerminus builds a
direct proposal locally and skips Ollama planning. This shortcut also applies to `--dry-run` and
`--explain`; direct-command inspection modes can complete without a live Ollama service as long as
direct detection succeeds.

## Planner flow

Natural-language requests that are not direct commands and are not blocked as ambiguous use the
planner. Planner calls Ollama with:

- a system prompt
- user prompt that includes request + route context + capability summaries

Planner parses model JSON into a strict `Proposal` schema. The model is asked to emit only
`structured` or `experimental` proposals and never executes commands itself.

Capability summaries include network-boundary metadata when any enabled command family is marked
`network_touching`. The planner prompt instructs the model to preserve that warning in proposal
notes, but the prompt is not a safety authority. Validator metadata, policy checks, preview,
confirmation, and executor boundaries remain the enforced path.

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

## Git inspection routing and planning

The deterministic router includes a `git_inspection` route category for clear read-only Git intent, such as status, current branch, recent commits, and diff summaries/file lists.

Planner proposals for Git in normal structured mode use the `git` family with a constrained argument shape:
- `{"operation": "status_short"}`
- `{"operation": "branch_current"}`
- `{"operation": "log_oneline", "count": <n>}`
- `{"operation": "diff_stat"}`
- `{"operation": "diff_name_only"}`

Mutating/network Git requests are intentionally not routed to `git_inspection` and remain unsupported or blocked by existing safety policy paths.

## Project health routing and planning

The router includes a `project_health` category for clear curated health intents such as running
tests, lint checks, format checks, docs builds, and evals.

Planner proposals for this route use structured `project_health` with a single closed enum
argument: `{"operation": "run_tests|lint_check|format_check|build_docs|run_evals"}`.

Requests for install/update/deploy/publish/arbitrary poetry commands, or write-formatting, are not
treated as safe project-health execution and remain unsupported/rejected by existing safety paths.

## Network diagnostics routing and planning

The deterministic router includes a `network_diagnostics` route category for clear read-only
network inspection intent, such as pinging a host a fixed number of times, showing HTTP headers for
an HTTP(S) URL, or looking up DNS records with `dig`/`nslookup`.

Planner proposals use structured families:

- `ping`: `{"host": "example.com", "count": 4}`
- `curl`: `{"operation": "http_head", "url": "https://example.com"}`
- `dig`: `{"domain": "example.com"}`
- `nslookup`: `{"domain": "example.com"}`

Network diagnostics contact external hosts. The planner prompt says only these read-only operations
are supported and disallows mutating HTTP methods, request bodies, arbitrary or secret-bearing
headers, cookies, downloads, scanning, SSH/SCP, nmap, wget, netcat, sudo network commands, and shell
pipelines/redirection. Validator checks remain authoritative.


## Deterministic local planner fast-path
For a small allowlist of unambiguous requests (for example: current directory, clear screen, list files, disk usage, and git status), OTerminus attempts deterministic local planning after routing and before the Ollama planner. On a local match, OTerminus produces a structured proposal and skips Ollama; validation, preview, confirmation, and execution policy still apply unchanged. If no conservative match exists, OTerminus falls back to the Ollama planner.
