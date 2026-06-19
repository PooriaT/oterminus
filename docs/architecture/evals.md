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

For real unsupported requests discovered during dogfooding, sanitize the request first using the
[Dogfooding playbook](../dogfooding-playbook.md) before creating or changing eval fixtures.

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
| `fast_path_local_planner.json` | Deterministic local-planner matches, including safe filesystem/text/process/Git inspection recipes, and no-match fallback behavior. |
| `filesystem_inspection.json` | Read-only filesystem inspection commands and planner proposals. |
| `filesystem_mutation.json` | Guarded filesystem write operations. |
| `git_inspection.json` | Read-only Git status, branch, log, and diff operations. |
| `macos_desktop.json` | macOS desktop/open behavior and URL rejection coverage. |
| `network_diagnostics.json` | Safe network diagnostics and unsupported network action rejection. |
| `planner_normalization.json` | Planner parsing, normalization, and direct-command boundary behavior. |
| `process_inspection.json` | Process listing and matching behavior. |
| `project_health.json` | Curated project test, lint, format, docs, and eval operations. |
| `release_smoke.json` | Cross-cutting public install and first-use proposal/validation smoke flows. |
| `system_inspection.json` | System inspection commands and environment-safety behavior. |
| `text_inspection.json` | Text/statistical inspection commands. |
| `unsafe_and_blocked.json` | Shell syntax, dangerous commands, unknown families, and policy blocks. |

Fixture IDs must be unique across all files. Prefer readable IDs prefixed with the capability or
behavior under test, such as `network-...`, `project-health-...`, `release-...`, `direct-...`,
`planner-...`, or `ambiguity-...`. Keep unsafe or rejected behavior grouped intentionally in the
capability file when it is capability-specific, or in `unsafe_and_blocked.json` when it exercises
generic policy or shell syntax blocking.

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

## Validating candidate files

Contributors can validate a proposed eval file before moving it into `evals/cases/`:

```bash
poetry run oterminus-evals --validate-file path/to/candidate.json
poetry run oterminus-evals --validate-file path/to/candidate.json --run
```

`--validate-file` checks JSON parsing, root-array shape, `EvalCase` schema validation, non-empty
content, and duplicate IDs within the candidate file. Candidate files can live anywhere, including a
temporary directory outside `evals/cases/`. Invalid candidates fail with concise errors that include
the candidate path and, for case-specific problems, the JSON array index.

By default, candidate validation checks shape only. Add `--run` to evaluate those candidate cases
through the same deterministic eval path used by the full fixture suite. Both modes are local-only:
they do not call Ollama, execute shell commands, inspect real project contents, require network
access, read audit logs, read persisted history, or depend on Git repository state.

## When to add eval cases

Add or update fixture cases when any of the following change:

- command support or capability behavior
- router or planner behavior
- validator or policy behavior
- direct-command detection behavior
- ambiguity detection behavior
- structured rendering behavior
- planner payload shape or parsing behavior
- public install or first-use behavior that should stay deterministic after packaging

Add both accepted and rejected cases when a capability has meaningful safety boundaries. Newer
command packs should include at least one representative accepted fixture plus focused rejection
coverage for unsupported flags, unsafe operations, broad targets, and command-family-specific policy
boundaries. Keep broad coverage expansion focused; small fixture additions are best paired with the
behavior change that needs regression protection.

Use `release_smoke.json` for small cross-cutting checks that protect public-install and first-use
behavior across direct commands, deterministic local planner paths, ambiguity blocking, and a minimal
planner-fixture path. These are still proposal/validation evals: they do not execute commands, do not
call Ollama, and do not inspect a real installed package. Keep command-family behavior in the
capability-specific fixture files, and use CLI tests for subprocess-style entry-point behavior such
as `oterminus --version`, `oterminus version`, and `oterminus doctor`.

## Adding cases for newer capabilities

Choose the fixture file by the capability or behavior under test:

- Put archive listing, extraction, creation, and archive-specific rejection cases in
  `archive_inspection.json`. Use a separate archive fixture only if archive coverage grows enough to
  justify a focused follow-up.
- Put ping, curl HEAD, DNS lookups, and network-specific rejection cases in
  `network_diagnostics.json`. Evals must never perform live network calls; use `planner_proposal` or
  direct-command detection only.
- Put read-only Git status, branch, log, and diff cases in `git_inspection.json`. Do not rely on the
  checkout being a Git repository because evals validate proposals and rendering only.
- Put curated test/lint/format-check/docs/eval operations in `project_health.json`. Project-health
  evals model preview and validation; they must not execute project commands.
- Put direct shell-like forms in `direct_commands.json` when direct detection is the behavior under
  test. Put generic shell syntax blocks, unknown families, package-manager installs, scans, and
  arbitrary project execution in `unsafe_and_blocked.json`.
- Put release-smoke cases in `release_smoke.json` only when the behavior crosses capability
  boundaries or protects public installation, CLI entry-point readiness, dry-run/explain previews,
  deterministic local planner first-use prompts, ambiguity lifecycle, or planner-fixture validation
  that should remain available without Ollama.
- Put accepted deterministic natural-language local-planner recipes in
  `fast_path_local_planner.json` without a `planner_proposal`. The eval runner must satisfy those
  cases through direct detection, ambiguity handling, or `plan_locally`; otherwise it fails before
  any mocked planner payload can be used. Include expected structured mode, command family, risk,
  acceptance, rendered command, and argv.
- Put vague user requests that must stop before planning in `ambiguity.json`; omit
  `planner_proposal` and set `expected_ambiguity_detected` plus a reason substring. Add a
  non-ambiguous contrast case when a nearby specific request should continue into planning.

For natural-language requests that would otherwise call the planner, include a deterministic
`planner_proposal` payload. The eval runner parses that payload locally, so fixtures must not depend
on Ollama, subprocess execution, real filesystem contents, network availability, current Git state,
or locally installed project tooling. Rejected structured payloads should use
`expected_planner_error_contains` when schema validation must fail before validator execution;
rejected command proposals should assert `expected_acceptance: false` and, when deterministic,
`expected_rendered_command` and `expected_argv`.

Split eval expansion into a separate PR or issue when one command pack needs broad matrix coverage,
multiple new fixture files, or exhaustive flag permutations. Prefer 30-60 high-value cases in a
single coverage PR and leave command-manual-level coverage for follow-ups.

## Relationship to tests

- Unit tests verify module behavior, loader errors, deterministic fixture ordering, and edge cases.
- Eval fixtures verify end-to-end proposal/validation invariants across representative prompts.
- Release-smoke CLI tests cover entry-point behavior that the eval harness does not model, including
  version and doctor commands.
- CI runs `poetry run oterminus-evals` alongside tests, lint, formatting, docs, and generated-doc
  checks.
