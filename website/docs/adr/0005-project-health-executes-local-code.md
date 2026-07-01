---
parse_number_prefixes: false
---

# ADR 0005: Project health workflows execute local code

## Status
Accepted

## Context
Users commonly ask OTerminus to run tests, lint checks, format checks, docs builds, and eval suites.
Although these are standard developer workflows, they can execute local project code and project tooling.

## Decision
Introduce a `project_health` capability as a curated boundary with enumerated operations only:
`run_tests`, `lint_check`, `format_check`, `build_docs`, `run_evals`.

PR #114 ships model metadata + structured shape scaffolding only. It does not ship executable rendering.
A future PR will add rendering plus explicit preview/confirmation enforcement.

## Consequences
- No arbitrary `poetry run ...` entrypoint is added.
- No arbitrary shell fragment execution is added via this capability.
- Capability docs can describe the boundary and risk before execution exists.
- Follow-up implementation can consume this metadata without changing safety posture.
