# Routing and Planning

OTerminus separates deterministic intent routing from model-based planning. The `doctor` CLI mode is
outside this request-planning path: it runs diagnostics and exits before routing or planner setup.
Before routing, OTerminus first checks for direct commands and then applies ambiguity detection to
non-direct natural-language requests.

First-run onboarding is also outside request planning. It is offered only for a bare interactive
REPL launch with missing persistent config and interactive stdin, then effective config is reloaded
before REPL services are built. One-shot direct commands, one-shot natural-language requests,
`--dry-run`, `--explain`, `doctor`, `version`, `completion`, and `config` commands do not run the
wizard and cannot be blocked by missing onboarding.

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
- `git_inspection`
- `network_diagnostics`
- `project_health`
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

Planner prompt context advertises only normal executable command families. Registry entries that are
planned/metadata-only (`experimental_only` with `direct_supported=false`) remain visible in detailed
help and generated references, but are filtered out of executable capability summaries, examples,
route suggestions, and structured argument shapes. This prevents the model from proposing command
families whose support has not graduated yet.

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

The registry exposes `project_health` as a structured capability for clear curated health intents
such as running tests, lint checks, format checks, docs builds, and evals. The planner context lists
only the operation enum: `run_tests`, `lint_check`, `format_check`, `build_docs`, and `run_evals`.

The deterministic router maps clear requests such as `run tests`, `run ruff check`,
`check formatting`, `run format check`, `build docs`, and `run evals` to the `project_health`
category when the project pack is enabled. The local planner can turn those requests into structured
proposals without Ollama; validation, preview, policy, and confirmation still run before execution.

Requests for install/update/deploy/publish/arbitrary poetry commands, or write-formatting, are not
treated as safe project-health execution and remain unsupported or rejected. Direct
`poetry run ...` input is not accepted as direct project-health support.

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
For a small allowlist of unambiguous requests, OTerminus attempts deterministic local planning after
routing and before the Ollama planner. On a local match, OTerminus produces a structured proposal
and skips Ollama; validation, preview, confirmation, and execution policy still apply unchanged. If
no conservative match exists, OTerminus falls back to the Ollama planner.

The local recipe set covers safe inspection only:

- filesystem inspection through `ls`, `du`, `df`, `stat`, and `file`
- system inspection through local manual-page lookup with `man`
- text inspection through `cat`, `head`, `tail`, `grep`, and `wc`
- process inspection through `ps` and `pgrep`
- Git inspection through read-only `git` operations
- existing REPL-like/project-health fast paths such as current directory, clear screen, and curated
  project checks

Representative requests include `show hidden files`, `show first 20 lines of README.md`,
`search TODO in src`, `show manual for ls`, `show manual section 5 for crontab`,
`find python processes`, `show current branch`, and `show git diff summary`.

Local planning is intentionally narrow. Rules are explicit Python checks, not a broad natural
language parser and not a shell-like parser. The helper foundation used by those rules normalizes
request text, rejects unsafe shell syntax, and can extract only simple parameters such as
conservative local path tokens, base-10 positive integers, and simple search terms. Extraction is
fail-closed: ambiguous numbers, multiline values, command substitution, shell operators,
redirection, wildcard syntax, URL-like path values, flag-like path values, and broad filesystem
roots are rejected by the helper or allowed to fall through to the Ollama planner path.
Manual-page recipes additionally require clear manual-page wording, a conservative topic token, and
an optional section from `1` through `9`; vague help or explanation requests do not become `man`
proposals.

Every local-planner match is built through the shared proposal builder. The builder checks registry
metadata first, so disabled command packs and platform-specific command availability are respected
before a proposal is created. It then validates typed structured arguments through the normal
`Proposal` and structured-command schemas. Invalid structured payloads do not produce local matches.
The proposal explanation includes the deterministic rule id and notes include
`Generated by deterministic local planner.`

The local planner does not add network, write, dangerous, Git mutation, process mutation, archive
mutation, or broad project-health recipes. Natural-language recipes also reject shell operators,
pipelines, redirection, command substitution, URL-like path values, wildcard path values, broad
roots, and zero or negative line counts instead of trying to reinterpret them.
