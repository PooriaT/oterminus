# Release and package publishing

OTerminus packaging and publication is intentionally staged:

1. local package build/install validation (PR #141)
2. TestPyPI validation publish (PR #142)
3. production PyPI publish (this workflow)

## Workflow map

- **TestPyPI:** `.github/workflows/publish-testpypi.yml` (manual `workflow_dispatch`)
- **Production PyPI:** `.github/workflows/publish-pypi.yml` (tag push `v*` only)

Production publishing is intentionally gated by release tags and a protected GitHub environment.

## Production workflow scope

The production workflow is designed to publish only intentional releases:

- Workflow file: `.github/workflows/publish-pypi.yml`
- Trigger: `push` tags matching `v*`
- No `pull_request` trigger
- No normal branch push trigger
- Auth model: GitHub Actions OIDC Trusted Publishing (no API token secret)
- GitHub environment: `pypi`

The workflow has separate jobs to build once and publish exact artifacts:

1. `build-distributions`
   - validates tag/version consistency (`vX.Y.Z` tag must match `tool.poetry.version`)
   - builds with `poetry build`
   - uploads `dist/` artifacts
2. `publish-pypi`
   - downloads the same artifacts
   - publishes with `pypa/gh-action-pypi-publish@release/v1`

## One-time Trusted Publisher setup

### TestPyPI pending publisher

Create or confirm the TestPyPI pending trusted publisher:

- **Project/package name:** `oterminus`
- **Owner:** `PooriaT`
- **Repository:** `oterminus`
- **Workflow filename:** `publish-testpypi.yml`
- **Environment name:** `testpypi`

### PyPI pending publisher

Create a production PyPI pending trusted publisher:

- **Project/package name:** `oterminus`
- **Owner:** `PooriaT`
- **Repository:** `oterminus`
- **Workflow filename:** `publish-pypi.yml`
- **Environment name:** `pypi`

### GitHub environment protection

In GitHub repository Settings → Environments:

1. create environment `pypi`
2. require manual approval before deployment
3. optionally restrict allowed branches/tags to release patterns

Do **not** add long-lived `PYPI_API_TOKEN` secrets when Trusted Publishing is available.

## Release checklist (production)

1. Confirm latest TestPyPI publish/install validation succeeded.
2. Update version in `pyproject.toml`.
3. Update changelog or release notes (if changelog is in use).
4. Run local release checks:

   ```bash
   poetry run pytest
   poetry run ruff check .
   poetry run ruff format --check .
   poetry run mkdocs build --strict
   poetry run oterminus-evals
   poetry build
   ```

5. Merge the release PR to `main`.
6. Create and push release tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

7. Approve the `pypi` environment deployment in GitHub Actions.
8. Verify package page on PyPI: `https://pypi.org/p/oterminus`
9. Verify install in a clean environment:

   ```bash
   python -m pip install oterminus
   oterminus --help
   oterminus doctor
   ```

## TestPyPI workflow scope (validation stage)

The TestPyPI workflow remains validation-only:

- Workflow file: `.github/workflows/publish-testpypi.yml`
- Trigger: manual (`workflow_dispatch`) only
- Target index: `https://test.pypi.org/legacy/`
- Auth model: GitHub Actions OIDC Trusted Publishing
- GitHub environment: `testpypi`

## Safety guarantees

- No production publish from pull requests.
- No production publish from ordinary branch pushes.
- Production releases require intentional `v*` tag creation.
- Production deployment requires `pypi` environment protection.
- Build and publish are separate; publish uses exact built artifacts.
- Version/tag mismatch fails before publish.
