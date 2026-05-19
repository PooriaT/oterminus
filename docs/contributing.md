# Contributing workflow

Use the same Poetry-based commands locally that CI runs on pull requests. The goal is to keep the
repository readable after the collapsed-file cleanup and to catch formatting, lint, test, docs, and
eval regressions before review.

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

Run deterministic eval fixtures when planner, router, validator, structured rendering, policy, or
command-family behavior changes:

```bash
poetry run oterminus-evals
```

These local test and eval commands should not require an Ollama service.

## Documentation rules

Update `/docs` in the same PR when you change behavior, architecture, command support,
configuration, policy, validation, evals, or user-facing behavior. Documentation is part of the
change, not follow-up work.

Keep documentation organized this way:

- Keep `README.md` as the landing page and quick orientation.
- Put detailed product, architecture, reference, eval, and contributor material under `/docs`.
- Update MkDocs navigation when adding, moving, or deleting docs pages.
- Do not include secrets, real tokens, real audit logs, or personal local paths in docs or fixtures.

Validate docs before review:

```bash
poetry run mkdocs build --strict
poetry run python scripts/check_docs_links.py
```

The docs workflow runs the strict build on pull requests and pushes to `main`, but deploys only
after a push to `main`.

## Pre-PR quality commands

Run the checks that match your change before opening a PR:

```bash
poetry run ruff format .
poetry run ruff format --check .
poetry run ruff check .
poetry run pytest --cov=src/oterminus --cov-report=term-missing
poetry run python scripts/check_docs_links.py
poetry run mkdocs build --strict
poetry run oterminus-evals
```

## PR checklist

- [ ] Python code is formatted with Ruff.
- [ ] Ruff format check and lint check pass.
- [ ] Tests pass with coverage (`poetry run pytest --cov=src/oterminus --cov-report=term-missing`).
- [ ] Docs are updated if behavior, architecture, command support, config, policy, validation,
      evals, or user-facing behavior changed.
- [ ] `poetry run mkdocs build --strict` and `poetry run python scripts/check_docs_links.py` pass.
- [ ] Evals are updated and run if planner, router, validator, policy, structured rendering, or
      command-family behavior changed.
- [ ] No secrets, real audit logs, tokens, or personal local paths were added to docs or fixtures.
