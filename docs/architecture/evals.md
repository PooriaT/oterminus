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
- expected ambiguity interception (when applicable)

## Fixture organization

Fixtures are JSON arrays under `evals/cases/*.json`, split by capability focus:

- `direct_commands.json`
- `filesystem_inspection.json`
- `filesystem_mutation.json`
- `text_inspection.json`
- `process_inspection.json`
- `system_inspection.json`
- `macos_desktop.json`
- `unsafe_and_blocked.json`
- `ambiguity.json`
- `planner_normalization.json`

All fixture IDs must be unique across all files. The eval loader reads every `*.json` file in sorted
filename order and preserves per-file case order.

## Fixture format

Core fields include:

- `id`
- `user_input`
- optional `planner_proposal`
- expected outputs (`expected_*` fields)

These evals are not live LLM tests. They are deterministic fixture checks. For planner-path cases,
`planner_proposal` supplies the mocked planner output payload. Ambiguity cases assert request
interception before planner parsing/validation.

## Running evals

```bash
poetry run oterminus-evals
poetry run oterminus-evals --fixtures-dir evals/cases
```

A non-zero exit code indicates at least one failing case. The eval command is CI-safe and does not require a running Ollama service, local model download, or network access.

## When to add eval cases

Add or update fixture cases when any of the following change:

- command support/capability behavior
- planner payload shape or parsing behavior
- validator or policy behavior
- ambiguity detection behavior
- direct-command detection behavior

## Relationship to tests

- unit tests verify module behavior and edge cases
- eval fixtures verify end-to-end proposal/validation invariants across representative prompts

- `fast_path_local_planner.json` validates deterministic local-planner matches and conservative no-match behavior without requiring Ollama.
