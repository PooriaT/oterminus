# Evals

OTerminus ships a deterministic, fixture-based eval harness for regression protection. The eval
command exercises direct-command detection, ambiguity detection, local planner fast paths, planner
proposal parsing, structured rendering, validation, and policy acceptance without calling Ollama.

## What evals cover

Fixture cases validate:

- expected proposal mode (`structured` or `experimental`)
- expected command family
- expected risk level
- expected acceptance or rejection
- expected rendered command and argv
- expected planner parse failures (when applicable)
- expected ambiguity interception (when applicable)
- deterministic local-planner matches and conservative no-match behavior

These evals are not live LLM tests. For planner-path cases, `planner_proposal` supplies the mocked
planner output payload. The runner parses that payload locally and validates the resulting proposal;
it does not call Ollama, download a model, or require network access.

## Fixture organization

Fixtures live under `evals/cases/*.json`. Each fixture file contains one JSON array, and each array
entry is one eval case. The default packaged command uses the mirrored files in
`src/oterminus/eval_fixtures/` so `oterminus-evals` also works from installed wheels.

Files are organized by capability or behavior:

| File | Purpose |
| --- | --- |
| `ambiguity.json` | Ambiguity gates and specific requests that must not be stopped as ambiguous. |
| `archive_inspection.json` | Archive list, extract, create, and archive-specific rejection behavior. |
| `direct_commands.json` | Shell-like inputs accepted directly without LLM planning. |
| `fast_path_local_planner.json` | Deterministic local-planner matches and no-match fallback behavior. |
| `filesystem_inspection.json` | Read-only filesystem inspection commands and planner proposals. |
| `filesystem_mutation.json` | Guarded filesystem write operations. |
| `git_inspection.json` | Read-only Git status, branch, log, and diff operations. |
| `macos_desktop.json` | macOS desktop/open behavior and URL rejection coverage. |
| `network_diagnostics.json` | Safe network diagnostics and unsupported network action rejection. |
| `planner_normalization.json` | Planner parsing, normalization, and direct-command boundary behavior. |
| `process_inspection.json` | Process listing and matching behavior. |
| `project_health.json` | Curated project test, lint, format, docs, and eval operations. |
| `system_inspection.json` | System inspection commands and environment-safety behavior. |
| `text_inspection.json` | Text/statistical inspection commands. |
| `unsafe_and_blocked.json` | Shell syntax, dangerous commands, unknown families, and policy blocks. |

Fixture IDs must be unique across all files. Prefer readable IDs prefixed with the capability or
behavior under test, such as `network-...`, `project-health-...`, `direct-...`, `planner-...`, or
`ambiguity-...`. Keep unsafe or rejected behavior grouped intentionally in the capability file when
it is capability-specific, or in `unsafe_and_blocked.json` when it exercises generic policy or shell
syntax blocking.

The eval loader reads every `*.json` file in sorted filename order and preserves per-file case order.
That ordering is deterministic and is covered by unit tests.

## Fixture format

Core fields include:

- `id`
- `user_input`
- optional `planner_proposal`
- expected outputs (`expected_*` fields)

Each fixture file must be a JSON array. Invalid JSON, non-array fixture files, invalid case shapes,
duplicate IDs, and empty fixture directories fail before eval execution. Loader error messages include
the fixture path, and invalid case-shape errors include the array index where practical.

When moving cases between files, preserve their expectations exactly unless the current implementation
proves a fixture is stale. Changing a fixture expectation means changing a regression contract and
should be documented in the pull request.

## Running evals

```bash
poetry run oterminus-evals
poetry run oterminus-evals --fixtures-dir evals/cases
```

A non-zero exit code indicates at least one failing case. The eval command is CI-safe and does not
require a running Ollama service, local model download, or network access.

## When to add eval cases

Add or update fixture cases when any of the following change:

- command support or capability behavior
- router or planner behavior
- validator or policy behavior
- direct-command detection behavior
- ambiguity detection behavior
- structured rendering behavior
- planner payload shape or parsing behavior

Add both accepted and rejected cases when a capability has meaningful safety boundaries. Keep broad
coverage expansion focused; small fixture additions are best paired with the behavior change that
needs regression protection.

## Relationship to tests

- Unit tests verify module behavior, loader errors, deterministic fixture ordering, and edge cases.
- Eval fixtures verify end-to-end proposal/validation invariants across representative prompts.
- CI runs `poetry run oterminus-evals` alongside tests, lint, formatting, docs, and generated-doc
  checks.
