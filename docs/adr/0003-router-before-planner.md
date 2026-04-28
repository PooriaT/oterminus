# ADR 0003: Router before planner

## Status
Accepted

## Context
Directly sending every natural-language request to planner increases ambiguity and can weaken intent steering.

## Decision
Run a deterministic capability router before planner invocation and pass route context into the planner prompt.

## Consequences
- Better planning hints and workflow classification.
- More predictable behavior for common request types.
- Router heuristics must be maintained alongside command metadata.
