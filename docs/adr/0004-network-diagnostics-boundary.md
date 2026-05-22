# ADR 0004: Network Diagnostics Boundary

## Status

Accepted.

## Context

OTerminus is local-first by default. Current curated command families inspect or mutate local
machine state under registry, validator, policy, preview, confirmation, and audit controls.

Network diagnostics are useful for troubleshooting connectivity and DNS behavior, but they contact
external systems. Even read-only diagnostics can reveal the user's IP address, DNS query, target
host, timing, and other network metadata to local network infrastructure, DNS resolvers, or remote
hosts.

Adding network diagnostics without an explicit architecture boundary would make it harder for
users, docs, prompts, discovery surfaces, and policy checks to tell when a command leaves the
local-machine-only comfort zone.

## Decision

Command specs can mark external-host contact with `network_touching=True`. The default is `False`
so existing command behavior remains unchanged.

Network-touching metadata is propagated through capability summaries, planner prompt context,
validation warnings, REPL help/discovery, and generated reference docs when such commands are
present.

Network diagnostics must start as read-only and constrained command families. They must not send
secrets, accept arbitrary secret-bearing headers, or support remote-state-changing methods such as
POST, PUT, or DELETE. Experimental mode must not be used as a shortcut for adding broad network
command access.

The validator remains authoritative. Metadata and prompt guidance can explain the boundary, but
commands still must pass registry allowlisting, command-shape validation, risk policy, preview, user
confirmation, and audit behavior before execution.

## Consequences

- Existing command families remain `network_touching=False`.
- This boundary does not add executable network diagnostics commands.
- Future network diagnostics can be introduced with explicit user-visible warnings instead of
  command-name heuristics.
- Documentation and generated references have a place to describe the external-host boundary.
- Future tests can assert both accepted read-only network diagnostics and rejected unsafe network
  forms without making real network calls.
