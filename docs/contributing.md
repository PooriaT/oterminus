# Contributing workflow

Use the same Poetry-based commands locally that CI runs on pull requests. The goal is to keep the
repository readable after the collapsed-file cleanup and to catch formatting, lint, test, docs, and
eval regressions before review.

## Public installs vs. development installs

End users should install released OTerminus packages from PyPI, preferably with
`pipx install oterminus` so the CLI is isolated from the system Python environment. If `pipx` is
unavailable, the user-facing fallback is `python -m pip install oterminus`. Keep these public
install instructions in README and the user guide aligned with actual package metadata and CLI
behavior.

Contributors working from a source checkout should use Poetry instead of a public PyPI install.

## Set up development dependencies

```bash
poetry install --with dev,docs
```

## Formatting and linting

Ruff is the Python formatter and linter for OTerminus. Do not add Black or another overlapping tool
for normal Python formatting or lint enforcement.

Format Python code before opening a PR:

```bash
poetry run ruff format .
```

Verify formatting without changing files:

```bash
poetry run ruff format --check .
```

Run lint checks across the repository:

```bash
poetry run ruff check .
```

Keep non-Python source readable too:

- Markdown should use normal headings, blank lines, lists, and valid fenced code blocks.
- YAML and TOML should stay expanded and reviewable, not collapsed into one-line files.
- Avoid mixing large formatting-only rewrites with feature or behavior changes; split them into a
  separate PR when practical.

## Tests and evals

Run the unit test suite locally:

```bash
poetry run pytest
```

CI reports package coverage with:

```bash
poetry run pytest --cov=src/oterminus --cov-report=term-missing
```

Run deterministic eval fixtures when command support, router/planner behavior, validator/policy
behavior, direct-command detection, ambiguity behavior, or structured rendering changes:

```bash
poetry run oterminus-evals
poetry run oterminus-evals --fixtures-dir evals/cases
```

Eval fixtures are JSON arrays organized by capability or behavior under `evals/cases/`, with a
packaged mirror under `src/oterminus/eval_fixtures/`. Keep fixture IDs unique across all files and
prefer readable capability or behavior prefixes such as `network-`, `project-health-`, `direct-`,
`release-`, `planner-`, or `ambiguity-`. New command-pack work should include representative eval
coverage for accepted behavior plus focused unsafe, unsupported, and ambiguous cases. Use
`release_smoke.json` only for cross-cutting public-install or first-use flows such as direct command
entry, deterministic local planner paths, ambiguity blocking, dry-run/explain preview behavior, or a
minimal planner-fixture path. Keep capability-specific behavior in its capability file, and cover
`oterminus --version`, `oterminus version`, and `oterminus doctor` with CLI tests because the eval
harness does not execute console-script commands.

Use `planner_proposal` for natural-language planner-path cases so the eval remains deterministic.
These local test and eval commands should not require an Ollama service, live network access, a real
Git repository state, filesystem contents, a real installed wheel, or subprocess execution. CI uses
the same deterministic fixture path, so no Ollama service/model/network call is required for the
regression gate. See [Evals](architecture/evals.md) for fixture organization and format details.

## CI coverage

The main CI workflow keeps Ubuntu as the full regression gate. It runs the complete pytest suite,
Ruff lint and format checks, deterministic evals, generated command-reference checks, docs link
checks, a strict MkDocs build, and `scripts/validate_package_install.py`.

CI also runs a separate macOS Python 3.13 platform smoke lane. That job is intentionally narrower:
it exercises platform-aware command registry behavior, direct-command detection, validator behavior,
shell completion/config tests, Ruff linting, and installed CLI smoke validation on a real macOS
runner. The macOS smoke lane does not require Ollama, local models, or natural-language planning,
and it does not publish packages or run release workflows.

## Documentation rules

Update `/docs` in the same PR when you change behavior, architecture, command support,
configuration, policy, validation, evals, or user-facing behavior. Documentation is part of the
change, not follow-up work.

Keep documentation organized this way:

- Keep `README.md` as the landing page and quick orientation.
- Put detailed product, architecture, reference, eval, and contributor material under `/docs`.
- Update MkDocs navigation when adding, moving, or deleting docs pages.
- Keep public install docs aligned with PyPI/pipx behavior, development docs aligned with Poetry,
  and release/package-validation docs aligned with the package validation script.
- Update the root `CHANGELOG.md` for user-facing changes.
- Release PRs must update `pyproject.toml` and `CHANGELOG.md` together.
- Do not include secrets, real tokens, real audit logs, persisted history files, or personal local
  paths in docs or fixtures.
- When audit, history, failure-explanation, output, install behavior, packaging metadata, or env
  privacy behavior changes, update the relevant docs in the same PR.

Validate docs before review:

```bash
poetry run mkdocs build --strict
poetry run python scripts/check_docs_links.py
poetry run python scripts/generate_command_reference.py --check
```

The docs workflow runs the strict build on pull requests and pushes to `main`, but deploys only
after a push to `main`.

## Pre-PR quality commands

Run the checks that match your change before opening a PR:

```bash
poetry run ruff format .
poetry run ruff format --check .
poetry run ruff check .
poetry run pytest
poetry run pytest --cov=src/oterminus --cov-report=term-missing
poetry run python scripts/check_docs_links.py
poetry run python scripts/generate_command_reference.py --check
poetry run mkdocs build --strict
poetry run oterminus-evals
poetry run python scripts/validate_package_install.py
```


## Local package build + wheel install validation

Validate local artifacts before publishing or changing packaging behavior. This script is for
release/development validation, not the primary user install path:

```bash
poetry run python scripts/validate_package_install.py
```

The script will:

1. remove stale local `dist/` artifacts, then build `sdist` and `wheel` with `poetry build`
2. create a temporary virtual environment
3. install the local wheel
4. verify `import oterminus`
5. run CLI smoke checks: `oterminus --help`, `oterminus --version`, `oterminus version`,
   `oterminus doctor`, config path/init/get/set/validate/show against a temporary config path,
   `oterminus completion zsh`, `oterminus completion bash`, `oterminus completion fish`, and
   `oterminus-evals`

Notes:

- `oterminus doctor` may exit non-zero or report Ollama readiness issues in clean or CI
  environments; this does not block packaging validation because the script still confirms CLI
  installability.
- `oterminus-evals` uses packaged fixture data from `src/oterminus/eval_fixtures/` so it works after wheel install.
- CI and the production PyPI workflow run the same package validation command before the production publish boundary.
- Publishing to TestPyPI and production PyPI is documented in `docs/release.md` and uses GitHub
  OIDC Trusted Publishing with protected deployment environments. The TestPyPI workflow still
  verifies the exact published version by installing it back from TestPyPI after publish.
- End-user installs should use `pipx install oterminus` after PyPI release; contributors should not add install-time or runtime behavior that automatically edits user shell startup files for completion.

## Pull request template and checklist

Every pull request should use `.github/pull_request_template.md` and keep every checklist item in
place. If an item is not applicable, mark it as `N/A` in the PR description instead of deleting it.

In addition to formatting, lint, test, docs, and eval checks, the PR template requires explicit
confirmation that core architecture invariants still hold for behavior-affecting changes (for
example capability-first command support, structured-first behavior, ambiguity gates, validator and
policy separation, and local-only audit logging expectations).

When command registry/spec files change, refresh generated command reference docs in the same PR.
When behavior, architecture, command support, config, evals, policy, validation, or user-facing
behavior changes, docs updates are mandatory in the same PR (not follow-up work).
