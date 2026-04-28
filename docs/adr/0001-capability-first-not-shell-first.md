# ADR 0001: Capability-first, not shell-first

## Status
Accepted

## Context
Unbounded shell support increases unsafe surface area, prompt complexity, and maintenance burden.

## Decision
Organize support around curated workflow capabilities and command families with explicit metadata (`risk`, `maturity`, flags, operand constraints).

## Consequences
- Better safety and explainability.
- More deterministic validation.
- Requires explicit curation work for each new command family.
