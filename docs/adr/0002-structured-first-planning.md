# ADR 0002: Structured-first planning

## Status
Accepted

## Context
Raw shell text from models is hard to constrain and validate safely.

## Decision
Prefer structured proposals (`command_family + arguments`) and deterministic Python rendering whenever supported.

## Consequences
- Safer execution path and stable previews.
- Cleaner regression fixtures.
- Requires ongoing schema/renderer maintenance for supported families.
