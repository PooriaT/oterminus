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
- network-touching command warnings when registry metadata marks the command
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

## Network-touching warning boundary

When a command spec sets `network_touching=True`, accepted previews include this warning:

`This command contacts external hosts and may reveal your IP address, DNS query, target host, or network metadata.`

The warning is informational and does not weaken existing checks. The command must still be in the
curated registry, pass command-shape validation, pass risk policy, and receive user confirmation
before execution. Experimental mode remains subject to the same network metadata and must not be
used as a shortcut to add broad network command access.

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
