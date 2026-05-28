# Release and package publishing

OTerminus release publishing is intentionally staged so the first public PyPI releases are
repeatable and safe.

## Workflow map

- **TestPyPI validation workflow:** `.github/workflows/publish-testpypi.yml`
  - trigger: manual `workflow_dispatch`
  - does **not** run on pull requests
  - publishes only to TestPyPI
- **Production PyPI workflow:** `.github/workflows/publish-pypi.yml`
  - trigger: pushed tags matching `v*`
  - does **not** run on pull requests
  - does **not** run on normal `main` pushes

## What is automatic (workflows)

### TestPyPI workflow automation

The TestPyPI workflow automatically:

1. installs dependencies with Poetry
2. runs release checks:
   - `poetry run pytest`
   - `poetry run ruff check .`
   - `poetry run ruff format --check .`
   - `poetry run mkdocs build --strict`
   - `poetry run oterminus-evals`
   - generated docs/reference check (if script exists)
   - docs link checker (if script exists)
3. builds distributions via `poetry build`
4. publishes artifacts to TestPyPI via OIDC Trusted Publishing
5. creates a clean virtualenv, installs the exact published version from TestPyPI (with short retries for index propagation), and runs smoke checks:
   - `oterminus --help`
   - `oterminus doctor`
   - `oterminus-evals`

Install command used post-publish:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "oterminus==<resolved-version>"
```

### Production PyPI workflow automation

The production workflow automatically:

1. validates tag/version consistency (`vX.Y.Z` must match `tool.poetry.version`)
2. runs the full regression gate:
   - `poetry run pytest`
   - `poetry run ruff check .`
   - `poetry run ruff format --check .`
   - `poetry run mkdocs build --strict`
   - `poetry run oterminus-evals`
   - generated docs/reference check
   - docs link checker
3. builds distributions once
4. publishes the exact built artifacts to PyPI after environment approval

Authentication is OIDC Trusted Publishing (`id-token: write`) with
`pypa/gh-action-pypi-publish`; no long-lived PyPI API tokens are required.

## Local package validation

Before publishing or changing packaging behavior, validate local artifacts from a source checkout:

```bash
poetry run python scripts/validate_package_install.py
```

This contributor/release-maintainer check builds the local `sdist` and `wheel`, installs the wheel
into a temporary clean virtual environment, verifies `import oterminus`, and runs installed-console
smoke checks such as `oterminus --help`, `oterminus doctor`, and `oterminus-evals`. It is not the
primary end-user install path; users should install released packages from PyPI with
`pipx install oterminus` or, when `pipx` is unavailable,
`python -m pip install oterminus`.

## Post-release user install verification

After a production PyPI release is available, verify the preferred end-user installation path with
`pipx` from a clean environment:

```bash
pipx install oterminus
oterminus --help
oterminus doctor
oterminus-evals
```

Also verify the pip fallback in a clean virtual environment:

```bash
python -m pip install oterminus
oterminus --help
oterminus doctor
```

For an existing `pipx` install, verify upgrades with:

```bash
pipx upgrade oterminus
oterminus doctor
```

The published package name is `oterminus`; the installed console scripts are `oterminus` and
`oterminus-evals`. `oterminus doctor` is the recommended post-install diagnostic and should clearly
report Ollama CLI, service, and local-model readiness. PyPI installation does not install or start
Ollama; natural-language planning still depends on a ready local Ollama setup, although direct
commands and some deterministic local paths may not need a live model.

Release verification should not add or rely on automatic shell startup-file changes. OTerminus
currently supports REPL Tab autocomplete via `prompt_toolkit`, but does not ship zsh, bash, or fish
shell-level completion scripts.

Note: `oterminus doctor` may exit non-zero in clean or CI environments if Ollama is unavailable;
this still confirms the installed CLI is callable and that readiness failures are surfaced clearly.

## What remains manual and intentional

The following steps are intentionally **manual** for release control:

- choose next release version
- update `pyproject.toml` version
- commit and push release version changes
- create and push `v*` release tag
- approve deployment in GitHub `pypi` environment

Manual release trigger commands:

```bash
poetry version patch
git add pyproject.toml poetry.lock
git commit -m "Release vX.Y.Z"
git push origin main
git tag vX.Y.Z
git push origin vX.Y.Z
```

These version/tag commands are intentionally manual for now.

## One-time Trusted Publisher + environment setup

### Create pending Trusted Publishers

For **TestPyPI**:

- project/package: `oterminus`
- owner: `PooriaT`
- repository: `oterminus`
- workflow filename: `publish-testpypi.yml`
- environment: `testpypi`

For **PyPI**:

- project/package: `oterminus`
- owner: `PooriaT`
- repository: `oterminus`
- workflow filename: `publish-pypi.yml`
- environment: `pypi`

### Create GitHub environments

In repository **Settings → Environments**:

1. create `testpypi`
2. create `pypi`
3. require manual approval for `pypi`
4. optionally restrict deployment branches/tags to release patterns

Do **not** add long-lived `PYPI_API_TOKEN` secrets when Trusted Publishing is configured.
