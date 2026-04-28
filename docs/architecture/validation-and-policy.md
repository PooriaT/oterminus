# Validation and Policy

Validation is the primary safety gate before any execution.

## Validation responsibilities

Validator enforces:

- proposal command-family existence in curated registry
- maturity-level restrictions (`blocked` rejected)
- structured rendering success for structured mode
- command parsing for experimental mode
- blocked shell operators/chaining/redirection/pipelines/substitution
- flag and operand constraints per command spec
- command-family/base-command consistency
- dangerous flag/target warnings and risk escalation
- forbidden operand prefixes (for example URL targets for `open`)
- allowed-root path restrictions when configured
- policy compatibility for computed risk level

## Policy model

Policy config fields:

- `mode`: `safe` / `write` / `dangerous`
- `allow_dangerous`: explicit dangerous enable switch
- `allowed_roots`: optional path allowlist

A command is accepted only when validation reasons are empty.

## Rejection behavior

If validation fails:

- preview includes rejection reasons
- execution is not prompted
- explain mode still reports blocked rationale

## Confirmation levels

- standard: default
- strong: dangerous risk
- very strong: experimental mode
