# Evals

OTerminus ships a deterministic fixture-based eval harness for regression protection.

## What evals cover

Fixture cases validate:

- expected proposal mode (`structured` or `experimental`)
- expected command family
- expected risk level
- expected acceptance/rejection
- expected rendered command and argv
- expected planner parse failures (when applicable)

## Fixture format

Fixtures are JSON arrays under `evals/cases/*.json`.

Core fields include:

- `id`
- `user_input`
- optional `planner_proposal`
- expected outputs (`expected_*` fields)

## Running evals

```bash
poetry run oterminus-evals
poetry run oterminus-evals --fixtures-dir evals/cases
```

A non-zero exit code indicates at least one failing case.

## Relationship to tests

- unit tests verify module behavior and edge cases
- eval fixtures verify end-to-end proposal/validation invariants across representative prompts
