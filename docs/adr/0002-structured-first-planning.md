# ADR 0002: Structured-first planning

## Status
Accepted

## Context
Free-form shell text from models is hard to constrain and validate safely.

## Decision
Support exactly two first-class proposal modes:

- `structured`: preferred for supported capabilities, using `command_family + arguments` and deterministic Python rendering.
- `experimental`: constrained fallback for single-command text that does not fit structured support yet.

Prefer structured proposals and deterministic Python rendering whenever supported. Experimental mode remains validated, policy-gated, previewed, and confirmed; it is not a shortcut around capability/renderer design. Legacy `"mode": "raw"` input is parse-boundary compatibility only, not an architectural mode.

## Consequences
- Safer execution path and stable previews.
- Cleaner regression fixtures.
- Requires ongoing schema/renderer maintenance for supported families.
- Contributors should add structured support for common safe workflows instead of relying on experimental fallback.
- Compatibility handling must not reintroduce raw as a public proposal mode.
