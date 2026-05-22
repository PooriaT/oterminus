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
- command-family/base-command consistency
- dangerous flag/target warnings and risk escalation
- forbidden operand prefixes (for example URL targets for `open`)
- allowed-root path restrictions when configured
- policy compatibility for computed risk level

Archive extraction is handled as an operation-specific write risk even though archive listing stays
safe. Validator accepts only the guarded forms `tar -xf <archive> -C <destination>` and
`unzip <archive> -d <destination>`, rejects missing destinations, `/`, broad system roots, shell
operators, URLs, wildcard archive paths, overwrite flags, path-transforming tar options, and
arbitrary archive flags. Accepted extraction previews include this warning:
`Archive extraction can write or overwrite files in the destination.`

These checks constrain command shape and policy boundaries; they do not inspect archive member paths
for traversal or other malicious content.

## Policy model

Policy config fields:

- `mode`: `safe` / `write` / `dangerous`
- `allow_dangerous`: explicit dangerous enable switch
- `allowed_roots`: optional path allowlist

A command is accepted only when validation reasons are empty. Validator and policy results are
authoritative for both structured and experimental proposals, including direct commands that skipped
LLM planning. Direct shell commands are not intercepted by natural-language ambiguity detection;
they continue to this validation and policy path.

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
