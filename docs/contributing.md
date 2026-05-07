# Contributing workflow

Use the same Poetry-based commands locally that CI runs on pull requests. These checks are intended
to be simple, whole-repository safeguards so formatting regressions, including collapsed one-line
Python files, are caught before review.

## Set up development dependencies

```bash
poetry install --with dev
```

The docs site also needs MkDocs packages. Install them into the Poetry environment before building
or serving docs locally:

```bash
poetry run python -m pip install mkdocs mkdocs-material
```

## Python formatting and linting

Ruff is the project's formatter and linter. Do not add Black or another overlapping lint tool for
normal Python formatting/lint enforcement.

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

## Tests

Run the unit test suite locally:

```bash
poetry run pytest
```

CI also reports coverage for the package with:

```bash
poetry run pytest --cov=src/oterminus --cov-report=term-missing
```

These test commands do not require an Ollama service.

## Documentation checks

Build docs strictly before opening a PR that changes documentation, navigation, or behavior that is
documented:

```bash
poetry run mkdocs build --strict
```

The docs workflow builds on pull requests and pushes to `main`, but deploys only after a push to
`main`.

## Recommended pre-PR checklist

```bash
poetry run ruff format .
poetry run ruff format --check .
poetry run ruff check .
poetry run pytest
poetry run mkdocs build --strict
```
