# Validation and Policy

Validation is the primary safety gate before any execution. It runs after direct-command detection,
capability routing/planning for natural-language requests, and structured rendering. Ambiguous
natural-language requests stop before validation because they do not produce a proposal.

## Validation responsibilities

Validator enforces:

- proposal command-family existence in curated registry
- maturity-level restrictions (`blocked` rejected)
- structured rendering success for structured mode
- command-text parsing and shell-shape checks for experimental mode
- blocked shell operators/chaining/redirection/pipelines/substitution
- flag and operand constraints per command spec
- trusted direct-origin flag policy opt-ins
- command-family/base-command consistency
- dangerous flag/target warnings and risk escalation
- network-touching command warnings when registry metadata marks the command
- platform support metadata from command specs and command packs
- forbidden operand prefixes (for example URL targets for `open`)
- allowed-root path restrictions when configured
- policy compatibility for computed risk level

Archive extraction and creation are handled as operation-specific write risks even though archive
listing stays safe. Validator accepts only the guarded extraction forms
`tar -xf <archive> -C <destination>` and `unzip <archive> -d <destination>`, and only the guarded
creation forms `tar -czf <archive_path> <source_paths...>` and
`zip -r <archive_path> <source_paths...>`.

For extraction, validation rejects missing destinations, `/`, broad system roots, shell operators,
URLs, wildcard archive paths, overwrite flags, path-transforming tar options, and arbitrary archive
flags. Accepted extraction previews include this warning:
`Archive extraction can write or overwrite files in the destination.`

For creation, validation rejects missing output archive paths, empty source lists, `/`, `.`, `..`,
broad system and home roots, wildcard source paths, shell operators, URLs, encryption/password
flags, split/archive-update/delete-source behavior, network archive destinations, and arbitrary
tar/zip flags. Accepted creation previews warn that the underlying archive tool may overwrite or
update an existing archive path. Experimental mode still goes through the same command-shape checks.

These checks constrain command shape and policy boundaries; they do not inspect archive member paths
for traversal or other malicious content.

Network diagnostics are accepted only for constrained read-only forms:

- `ping -c <count> <host>` with count from 1 to 10
- `curl -I <http-or-https-url>`
- `dig <domain>`
- `nslookup <domain>`

Validation rejects ping without a count, excessive ping counts, ping flood/unlimited forms, URLs as
ping targets, non-HEAD curl behavior, POST/PUT/PATCH/DELETE, request bodies, arbitrary headers,
authorization, cookies, downloads/output files, file URLs, arbitrary DNS lookup flags, unsupported
network tools, shell operators, pipelines, and redirection.

## Direct flag policy

Command specs default to `direct_flag_policy=explicit`, so direct commands and planner proposals use
the same curated flag metadata unless a command opts in. The first opt-in is `ls`, which uses
`safe_inspection_passthrough` only for proposals whose origin is trusted local direct-command
detection. That policy accepts conservative short flag clusters such as `-ltrh`, conservative long
options such as `--color=auto`, and local path operands while preserving the typed structured `ls`
schema for natural-language planning.

Planner JSON, proposal notes, summaries, explanations, and command text cannot choose this trusted
origin. Local-planner, Ollama-planner, unknown, or reconstructed proposals continue through explicit
flag validation, and every command without the opt-in remains strict.

## Network-touching warning boundary

When a command spec sets `network_touching=True`, accepted previews include this warning:

`This command contacts external hosts and may reveal your IP address, DNS query, target host, or network metadata.`

The warning is informational and does not weaken existing checks. The command must still be in the
curated registry, pass platform support checks, pass command-shape validation, pass risk policy, and
receive user confirmation before execution. Network-touching commands never qualify for safe
auto-execute. Experimental mode remains subject to the same network
metadata and must not be used as a shortcut to add broad network command access.

## Policy model

Policy config fields:

- `mode`: `safe` / `write` / `dangerous`
- `allow_dangerous`: explicit dangerous enable switch
- `allowed_roots`: optional path allowlist

A command is accepted only when validation reasons are empty. Validator and policy results are
authoritative for both structured and experimental proposals, including direct commands that skipped
LLM planning. Direct shell commands are not intercepted by natural-language ambiguity detection;
they continue to this validation and policy path.

Experimental validation emits the user-facing preview warning:
`Experimental command: this was not rendered from typed structured arguments. Review it carefully before running.`
Verbose previews may additionally show the architecture diagnostic:
`Experimental mode stays outside deterministic structured rendering and uses stricter confirmation.`
The diagnostic is not a normal validation warning.

## Rejection behavior

If validation fails:

- preview includes rejection reasons
- execution is not prompted
- explain mode still reports blocked rationale

## Confirmation levels

- standard: default
- strong: dangerous risk
- very strong: experimental mode

Experimental mode does not bypass validation or policy. It exists only as a constrained fallback
when structured rendering is unavailable or unsuitable.

`OTERMINUS_AUTO_EXECUTE_SAFE=true` is an explicit, environment-only exception to the default prompt.
It does not change validation or risk computation. It is considered only after a successful preview
for execute-mode requests and only for direct-detected or deterministic local-planner structured
proposals with exact `safe` risk, no warnings, no rejection reasons, a rendered command/argv, and an
enabled platform-supported command spec. Warnings, network metadata, write/dangerous risk,
experimental mode, Ollama-planned proposals, project health, archive extraction/creation, history
reruns, dry-run, and explain mode all fail closed to the normal confirmation behavior.

## Project health risk boundary

Project-health checks are common developer workflows, but they are not passive inspection:
pytest/evals/docs/tooling may execute repository code. Validation accepts project-health only through
structured rendering of the curated operations (`run_tests`, `lint_check`, `format_check`,
`build_docs`, `run_evals`) into exact command argv forms.

Validation rejects arbitrary project tooling commands (for example unsupported `poetry run ...`,
package installation/update commands, publish/deploy commands, and write-formatting such as
`poetry run ruff format .`). Accepted project-health proposals carry a warning that local project
code/tooling may execute and remain write-risk with explicit preview + confirmation requirements.
Only `poetry run ruff format --check .` is supported for formatting, and only via the
`format_check` structured operation.
