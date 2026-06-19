# Release and package publishing

OTerminus release publishing is intentionally staged so the first public PyPI releases are
repeatable and safe.

Release notes are tracked in the root
[`CHANGELOG.md`](https://github.com/PooriaT/oterminus/blob/main/CHANGELOG.md). Keep the changelog
entry for the target version accurate before tagging a release; do not mark a version as released
until the production PyPI release is complete.

## Release checklist

Use this checklist for each release, starting with `0.1.2`. The workflow details below remain the
source of truth for TestPyPI, production PyPI, Trusted Publishing, and protected environments.

### Pre-release

- Confirm all target issues and pull requests for the release are merged.
- Update `CHANGELOG.md` for the target version.
- Update `pyproject.toml` to the target version.
- Run the full local regression gate:

```bash
poetry run pytest
poetry run ruff check .
poetry run ruff format --check .
poetry run mkdocs build --strict
poetry run oterminus-evals
poetry run python scripts/generate_command_reference.py --check
poetry run python scripts/check_docs_links.py
```

The deterministic eval gate includes `release_smoke.json`, which protects public-install and
first-use proposal/validation flows without calling Ollama, touching the network, executing shell
commands, or requiring a real installed package. Keep doctor and version readiness covered by CLI
tests and installed-package smoke checks rather than eval fixtures.

- Build the package:

```bash
poetry build
```

- Validate local wheel installation:

```bash
poetry run python scripts/validate_package_install.py
```

- Optionally validate TestPyPI when packaging metadata, package contents, console scripts, or
  install behavior changed.

If `scripts/generate_command_reference.py` or `scripts/check_docs_links.py` is not present on a
future branch, skip the missing script and document the reason in the release PR.

### Release

- Commit the version and changelog updates together.
- Create and push a matching tag, for example `v0.1.2`.
- Confirm the production PyPI workflow validates tag/version consistency.
- Approve the protected `pypi` environment deployment if configured.

### Post-release

- Verify the PyPI project page at `https://pypi.org/project/oterminus/`.
- Verify either a fresh `pipx` install or an upgrade of an existing `pipx` install:

```bash
pipx install oterminus
oterminus --version
oterminus doctor
oterminus-evals
```

```bash
pipx upgrade oterminus
oterminus --version
oterminus doctor
oterminus-evals
```

- Verify the pip fallback install in a clean virtual environment:

```bash
python -m pip install oterminus
oterminus --version
oterminus doctor
oterminus-evals
```

- Update GitHub release notes if using GitHub Releases.

## Workflow map

- **Main CI workflow:** `.github/workflows/ci.yml`
  - trigger: pull requests and pushes to `main`
  - Ubuntu job is the full regression gate
  - macOS job is a focused platform smoke lane for platform-aware registry behavior and installed
    CLI basics
  - does **not** publish to TestPyPI or PyPI
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
5. creates a clean virtualenv, installs the exact published version from TestPyPI (with short
   retries for index propagation), and runs smoke checks:
   - `oterminus --help`
   - `oterminus --version`
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
3. runs local installed-package validation with
   `poetry run python scripts/validate_package_install.py`
4. uploads the validated `dist/` artifacts
5. publishes the exact validated artifacts to PyPI after environment approval

Authentication is OIDC Trusted Publishing (`id-token: write`) with
`pypa/gh-action-pypi-publish`; no long-lived PyPI API tokens are required.

## Local package validation

Before publishing or changing packaging behavior, validate local artifacts from a source checkout:

```bash
poetry run python scripts/validate_package_install.py
```

This contributor/release-maintainer check builds the local `sdist` and `wheel`, installs the wheel
into a temporary clean virtual environment, verifies `import oterminus`, and runs installed-console
smoke checks such as `oterminus --help`, `oterminus --version`, `oterminus version`,
`oterminus doctor`, config path/init/get/set/reset/validate/show checks, shell completion rendering,
and `oterminus-evals`. `oterminus doctor` may exit non-zero in CI when Ollama is unavailable; the
validation still confirms the installed CLI is callable and installable. The script uses temporary
paths for smoke-check config, audit, and history files and does not publish anything.
It is not the primary end-user install path; users should install released packages from PyPI with
`pipx install oterminus` or, when `pipx` is unavailable, `python -m pip install oterminus`.

The main CI workflow runs the same package validation command in the Ubuntu full regression gate
after the normal tests, lint, evals, generated docs checks, docs link checks, and strict docs build.
Its macOS smoke lane also runs the package validation command to verify installed CLI basics on a
real macOS runner without requiring Ollama or publishing artifacts. The production release workflow
runs package validation before uploading artifacts for PyPI publishing. The TestPyPI workflow still
verifies the exact published version by installing it back from TestPyPI after publish.

## Post-release user install verification

After a production PyPI release is available, verify the preferred end-user installation path with
`pipx` from a clean environment:

```bash
pipx install oterminus
oterminus --help
oterminus --version
oterminus doctor
oterminus-evals
```

Also verify the pip fallback in a clean virtual environment:

```bash
python -m pip install oterminus
oterminus --help
oterminus --version
oterminus doctor
```

For an existing `pipx` install, verify upgrades with:

```bash
pipx upgrade oterminus
oterminus --version
oterminus doctor
```

The published package name is `oterminus`; the installed console scripts are `oterminus` and
`oterminus-evals`. `oterminus --version` confirms the installed package version without requiring
Ollama; `oterminus doctor` is the recommended post-install readiness diagnostic and should clearly
report installed package version, Python executable, install context, Ollama CLI, service,
local-model readiness, selected model, and config/audit/history path status. PyPI installation does
not install or start Ollama; natural-language planning still depends on a ready local Ollama setup,
although direct commands and some deterministic local paths may not need a live model.

Release verification should not add or rely on automatic shell startup-file changes. OTerminus
supports REPL Tab autocomplete via `prompt_toolkit` and prints opt-in zsh, bash, and fish
shell-level completion scripts with `oterminus completion <shell>`.

Note: `oterminus doctor` may exit non-zero in clean or CI environments if Ollama is unavailable;
this still confirms the installed CLI is callable and that readiness failures are surfaced clearly.

## What remains manual and intentional

The following steps are intentionally **manual** for release control:

- choose next release version
- update `CHANGELOG.md`
- update `pyproject.toml` version
- run the full local regression gate
- build package distributions and validate local wheel installation
- commit and push release version/changelog changes
- create and push `v*` release tag
- approve deployment in GitHub `pypi` environment

Manual release trigger commands:

```bash
poetry version X.Y.Z
git add CHANGELOG.md pyproject.toml poetry.lock
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
