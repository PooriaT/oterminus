# Release and package publishing

OTerminus packaging and publication is intentionally staged:

1. local package build/install validation (completed in PR #141)
2. **TestPyPI validation publish** (this workflow)
3. production PyPI publish (separate, later PR/issue)

This page documents step 2 only.

## TestPyPI workflow scope

The TestPyPI workflow exists to validate package publication and install behavior without publishing to
production PyPI.

- Workflow file: `.github/workflows/publish-testpypi.yml`
- Trigger: manual (`workflow_dispatch`) only
- Target index: `https://test.pypi.org/legacy/`
- Auth model: GitHub Actions OIDC Trusted Publishing (no API token secret)
- GitHub environment: `testpypi`

TestPyPI publishing is validation-only. Production PyPI publication is intentionally handled later in a
separate issue/PR.

## One-time Trusted Publisher setup (TestPyPI)

TestPyPI and PyPI are separate services with separate accounts. Sign in to TestPyPI and configure a
pending Trusted Publisher for OTerminus:

- **Project/package name:** `oterminus`
- **Owner:** `PooriaT`
- **Repository:** `oterminus`
- **Workflow name/path:** `.github/workflows/publish-testpypi.yml`
- **Environment name:** `testpypi`

Also create a GitHub repository Environment named `testpypi` (Settings → Environments). This workflow
uses that environment for deployment context and OIDC trust matching.

Do **not** add long-lived `PYPI_*` or `TEST_PYPI_*` API token secrets for this workflow when Trusted
Publishing is available.

## Run a TestPyPI publish

1. Open GitHub Actions for this repository.
2. Select **Publish to TestPyPI**.
3. Click **Run workflow** on your target branch/tag.
4. Confirm the `build-distributions` job passes and `publish-testpypi` succeeds.

The workflow builds distributions with `poetry build`, uploads artifacts, then publishes the same built
artifacts to TestPyPI.

## Verify on TestPyPI

After a successful run:

1. Open package page: `https://test.pypi.org/p/oterminus`
2. Confirm expected version/files (`.whl` and `.tar.gz`) are present.

## Install test from TestPyPI

Use a clean virtual environment and install from TestPyPI:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ oterminus
```

`--extra-index-url https://pypi.org/simple/` is often required because TestPyPI may not host every
transitive runtime dependency needed by `oterminus`.

## Safety guarantees in this stage

- No `pull_request` trigger.
- No production PyPI target.
- No API token secret requirement.
- No version mutation or auto-release from every push.
- Build must succeed and `dist/` artifacts must exist before publish.
