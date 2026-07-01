# Docusaurus Migration Plan

This document audits the current MkDocs documentation site and defines the staged plan for moving
OTerminus documentation to Docusaurus. It is intentionally planning-only: it does not add
Docusaurus, move content, change CI, or change the GitHub Pages deployment.

## Purpose

The migration should make the documentation site easier to evolve as a product and contributor
handbook while keeping the Python package, release workflows, generated reference docs, and public
documentation URL stable during the transition.

Docusaurus is a good target because it gives the project a dedicated documentation app, a typed
configuration surface, sidebar control, built-in versionable structure if needed later, and a Node
toolchain that can be isolated from the Python package.

## Non-goals

- Do not add a `website/` directory in this PR.
- Do not add `package.json`, `package-lock.json`, Docusaurus config, sidebars, or Node CI in this
  PR.
- Do not move or rename existing Markdown docs in this PR.
- Do not remove MkDocs dependencies or update Poetry metadata in this PR.
- Do not change `.github/workflows/*` in this PR.
- Do not change the live GitHub Pages URL or deployment behavior in this PR.
- Do not change runtime Python code or generated command-reference behavior in this PR.

## Current MkDocs Inventory

The current site is configured by `mkdocs.yml`:

- `site_url` is `https://pooriat.github.io/oterminus/`.
- The theme is `material`.
- The only configured MkDocs plugin is `search`.
- Markdown extensions are `admonition`, `pymdownx.superfences` with a custom `mermaid` fence, and
  `toc` with permalinks.
- Extra JavaScript loads `docs/assets/javascripts/mermaid-fallback.js`.
- CI installs docs dependencies with `poetry install --with dev,docs`.
- `.github/workflows/ci.yml`, `.github/workflows/publish-pypi.yml`, and
  `.github/workflows/publish-testpypi.yml` run `poetry run mkdocs build --strict`.
- `.github/workflows/docs.yml` builds MkDocs on docs PRs and deploys the `site` artifact to GitHub
  Pages on pushes to `main`.
- `scripts/check_docs_links.py` assumes `DOCS_DIR = docs`, scans `README.md` and `docs/**/*.md`,
  and validates `mkdocs.yml` nav targets.
- `scripts/generate_command_reference.py` writes generated files to `docs/reference/`.

The repo also contains `docs/adr/0005-project-health-executes-local-code.md`, but that page is not
currently in `mkdocs.yml` nav. The migration should decide whether to add it to the Docusaurus
sidebar or leave it unlisted.

## Current Nav Page Inventory

This table uses the current `mkdocs.yml` navigation as the source of truth.

| Current path | Proposed Docusaurus path | Nav section | Likely MDX conversion | Mermaid | Admonitions | Generated | Important inbound links |
|---|---|---|---|---|---|---|---|
| `docs/index.md` | `website/docs/index.md` with `slug: /` | Home | no | no | no | no | yes |
| `docs/product/what-is-oterminus.md` | `website/docs/product/what-is-oterminus.md` | Product | no | no | no | no | yes |
| `docs/product/user-guide.md` | `website/docs/product/user-guide.md` | Product | no | no | no | no | yes |
| `docs/product/shell-completion.md` | `website/docs/product/shell-completion.md` | Product | no | no | no | no | yes |
| `docs/product/supported-workflows.md` | `website/docs/product/supported-workflows.md` | Product | no | no | no | no | yes |
| `docs/product/policy-modes.md` | `website/docs/product/policy-modes.md` | Product | no | no | no | no | yes |
| `docs/architecture/overview.md` | `website/docs/architecture/overview.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/request-lifecycle.md` | `website/docs/architecture/request-lifecycle.md` | Architecture | yes | yes | no | no | yes |
| `docs/architecture/routing-and-planning.md` | `website/docs/architecture/routing-and-planning.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/validation-and-policy.md` | `website/docs/architecture/validation-and-policy.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/execution.md` | `website/docs/architecture/execution.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/structured-rendering.md` | `website/docs/architecture/structured-rendering.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/capability-system.md` | `website/docs/architecture/capability-system.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/command-registry.md` | `website/docs/architecture/command-registry.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/observability.md` | `website/docs/architecture/observability.md` | Architecture | no | no | no | no | yes |
| `docs/architecture/evals.md` | `website/docs/architecture/evals.md` | Architecture | no | no | no | no | yes |
| `docs/reference/config.md` | `website/docs/reference/config.md` | Reference | no | no | no | no | yes |
| `docs/reference/capability-map.md` | `website/docs/reference/capability-map.md` | Reference | no | no | no | yes | yes |
| `docs/reference/command-families.md` | `website/docs/reference/command-families.md` | Reference | no | no | no | yes | yes |
| `docs/reference/audit-log-schema.md` | `website/docs/reference/audit-log-schema.md` | Reference | no | no | no | no | yes |
| `docs/contributing.md` | `website/docs/contributing.md` | Contributing | no | no | no | no | yes |
| `docs/dogfooding-playbook.md` | `website/docs/dogfooding-playbook.md` | Contributing | no | no | no | no | yes |
| `docs/release.md` | `website/docs/release.md` | Contributing | no | no | no | no | yes |
| `docs/adding-command-families.md` | `website/docs/adding-command-families.md` | Contributing | no | no | no | no | yes |
| `docs/adr/0001-capability-first-not-shell-first.md` | `website/docs/adr/0001-capability-first-not-shell-first.md` | ADRs | no | no | no | no | yes |
| `docs/adr/0002-structured-first-planning.md` | `website/docs/adr/0002-structured-first-planning.md` | ADRs | no | no | no | no | no |
| `docs/adr/0003-router-before-planner.md` | `website/docs/adr/0003-router-before-planner.md` | ADRs | no | no | no | no | no |
| `docs/adr/0004-network-diagnostics-boundary.md` | `website/docs/adr/0004-network-diagnostics-boundary.md` | ADRs | no | no | no | no | no |

Important inbound links means there are current links from `README.md` or another docs page that
should be preserved or redirected during migration.

## Target Repository Shape

Use a side-by-side Docusaurus app under `website/`:

```text
website/
  package.json
  package-lock.json
  docusaurus.config.ts
  sidebars.ts
  tsconfig.json
  src/
    css/
      custom.css
  static/
    .nojekyll
  docs/
    index.md
    product/
    architecture/
    reference/
    contributing/
    adr/
```

`website/` is preferred over placing Docusaurus files at the repo root because OTerminus is a Python
package first. Keeping Docusaurus in `website/` isolates Node dependency files, TypeScript config,
static assets, build output, and future frontend tooling from Poetry packaging, Python linting, and
release workflows. It also makes it easier for CI to cache and run Python and Node jobs separately.

Recommended content shape:

- Move the current `docs/index.md` content to `website/docs/index.md` and give that doc an
  explicit root slug, for example `slug: /`.
- Configure Docusaurus docs routing so docs are served at the repository site root, not under a
  new `/docs/` prefix. If the migration chooses not to use docs-root routing, add an equivalent
  `website/src/pages/index.*` redirect or landing page so `https://pooriat.github.io/oterminus/`
  continues to show the current documentation landing content.
- Preserve product and architecture paths under `website/docs/product/` and
  `website/docs/architecture/`.
- Preserve reference paths under `website/docs/reference/`.
- Either keep contributing docs at top level under `website/docs/` or place them under
  `website/docs/contributing/`. The first migration should prefer minimal URL churn, so keep the
  current filenames unless Docusaurus sidebar ergonomics require a directory.
- Preserve ADR filenames under `website/docs/adr/`.

## URL and GitHub Pages Policy

The public site must remain:

```text
https://pooriat.github.io/oterminus/
```

The intended Docusaurus config is:

```ts
url: 'https://pooriat.github.io',
baseUrl: '/oterminus/',
organizationName: 'PooriaT',
projectName: 'oterminus',
trailingSlash: false,
presets: [
  [
    'classic',
    {
      docs: {
        routeBasePath: '/',
        sidebarPath: './sidebars.ts',
      },
    },
  ],
],
```

GitHub Pages should continue to deploy from GitHub Actions. The current repo already has
`.github/workflows/docs.yml`, which uses `actions/configure-pages`, `actions/upload-pages-artifact`,
and `actions/deploy-pages` to deploy MkDocs output from `site` after pushes to `main`.

Migration PRs should not switch the Pages artifact path until the Docusaurus build is present,
link-checked, and verified in CI. The deployment PR should change the artifact from MkDocs `site` to
the Docusaurus build output, normally `website/build`. Before that switch, verify that the built
site root at `/oterminus/` renders the migrated `docs/index.md` landing content rather than a
Docusaurus default page, `/intro`, or `/docs/intro`.

## Conversion Risks and Mitigations

| Risk | Current source | Mitigation |
|---|---|---|
| MkDocs Material admonitions may not render the same way in Docusaurus. | `mkdocs.yml` enables `admonition`, although current nav docs do not contain `!!!` admonition blocks. | Scan again during content migration. Convert any future admonitions to Docusaurus admonition syntax or MDX components. |
| `pymdownx.superfences` behavior is MkDocs-specific. | `mkdocs.yml` configures `pymdownx.superfences` and a custom `mermaid` fence. | Verify all fenced blocks under Docusaurus. Avoid relying on PyMdown-specific fence behavior. |
| Mermaid rendering changes. | `docs/architecture/request-lifecycle.md` contains a Mermaid fence. | Enable Docusaurus Mermaid support and visually verify the request lifecycle diagram. Convert to MDX only if the Markdown fence is insufficient. |
| Mermaid fallback script becomes obsolete or incompatible. | `docs/assets/javascripts/mermaid-fallback.js` depends on MkDocs Material navigation hooks such as `document$`. | Do not carry this script forward by default. Replace it with native Docusaurus Mermaid support. |
| Heading anchors can change. | `toc.permalink` and MkDocs slug generation currently define anchors used by docs links. | Run a Docusaurus build and link checker, then fix or redirect changed anchors. Pay special attention to links with fragments. |
| Markdown links use `.md` paths. | README and docs link heavily to `docs/**/*.md` and relative `.md` targets. | Decide whether source links remain repository-oriented or become site-oriented. During migration, update copied Docusaurus docs to Docusaurus-friendly relative links and keep README source links valid. |
| Generated reference files currently live under `docs/reference/`. | `scripts/generate_command_reference.py` writes `capability-map.md` and `command-families.md` there. | Add a configurable docs root before moving generated output. Keep old output checked until MkDocs is retired. |
| README links point into `docs/`. | `README.md` links to product, architecture, reference, contributing, dogfooding, release, command-family, and eval docs. | Keep README links valid for source browsing throughout the transition. Update any site URL references only in the deployment PR. |
| `scripts/check_docs_links.py` assumes `DOCS_DIR = docs`. | The checker scans `README.md`, `docs/**/*.md`, and `mkdocs.yml` nav targets. | Teach the checker about a configurable docs root or a Docusaurus mode before enforcing Docusaurus docs. |
| Release workflows still run MkDocs strict builds. | CI, TestPyPI, and PyPI workflows all run `poetry run mkdocs build --strict`. | Keep MkDocs green until the final cleanup PR. Switch release workflows only after Docusaurus deployment is verified. |

## Generated Reference Strategy

Use a staged generated-reference migration:

1. Keep generated files under `docs/reference/` while MkDocs remains the deployed site.
2. Add a configurable output root to `scripts/generate_command_reference.py`, for example a
   `--docs-root` option defaulting to `docs`.
3. During side-by-side migration, generate and check the same reference content for both
   `docs/reference/` and `website/docs/reference/` if the content is duplicated.
4. Prefer checking generated Docusaurus reference files in CI before Pages deployment, but keep the
   existing MkDocs generated-reference check intact.
5. Stop updating `docs/reference/` only in the final MkDocs cleanup PR, after Docusaurus is deployed
   to GitHub Pages and release workflows no longer build MkDocs.

Generated files should eventually move to `website/docs/reference/`, but only after the Docusaurus
site is the deployed source of truth. Until then, the old files remain part of the live docs build.

## Link-checking Strategy

The current checker should continue to protect `README.md`, `docs/**/*.md`, and `mkdocs.yml` nav
targets while MkDocs is live.

For Docusaurus, add a staged checker update:

1. Extend `scripts/check_docs_links.py` to accept a docs root, nav/sidebar source, or explicit mode.
2. Keep repository-relative README links valid during the side-by-side phase.
3. Check copied Docusaurus docs under `website/docs/**/*.md` and `website/docs/**/*.mdx`.
4. Add sidebar target validation for `website/sidebars.ts`.
5. Validate anchor fragments after Docusaurus build because heading slug behavior can differ from
   MkDocs.
6. Treat generated reference output as stale if either the live MkDocs docs or the Docusaurus docs
   are expected to contain generated copies during the transition.

## Recommended PR Sequence

### 1. Audit and migration plan

Scope:

- Add this plan.
- Inventory the current MkDocs nav, workflows, generated docs, and migration risks.
- Do not change the site implementation.

Dependencies:

- Current MkDocs site and workflows.

Acceptance criteria:

- The plan covers purpose, non-goals, nav inventory, target structure, URL policy, generated docs,
  link checks, risks, staged PRs, and cleanup criteria.
- Existing MkDocs docs checks still pass.

Validation commands:

```bash
poetry run python scripts/check_docs_links.py
poetry run python scripts/generate_command_reference.py --check
poetry run mkdocs build --strict
```

### 2. Side-by-side Docusaurus scaffold

Scope:

- Add `website/` with Docusaurus, TypeScript config, sidebar skeleton, custom CSS, and
  `static/.nojekyll`.
- Keep MkDocs as the deployed site.
- Add Node install and build documentation, but do not deploy Docusaurus yet.

Dependencies:

- Audit plan from PR 1.

Acceptance criteria:

- `website/` installs reproducibly with `package-lock.json`.
- Docusaurus builds with placeholder or minimally copied docs.
- Python package metadata and MkDocs deployment remain unchanged.

Validation commands:

```bash
cd website
npm ci
npm run build
```

### 3. Content and navigation migration

Scope:

- Copy or move current docs content into `website/docs/`.
- Build `sidebars.ts` from the current MkDocs nav sections.
- Configure Mermaid support.
- Update copied links for Docusaurus source and route behavior.
- Add configurable generated-reference output if generated docs are copied.

Dependencies:

- Side-by-side Docusaurus scaffold.

Acceptance criteria:

- Docusaurus sidebar covers the current MkDocs nav pages.
- `docs/architecture/request-lifecycle.md` Mermaid content renders in Docusaurus.
- Generated reference pages are present and checked for the Docusaurus docs root.
- README and source docs links remain valid.

Validation commands:

```bash
poetry run python scripts/check_docs_links.py
poetry run python scripts/generate_command_reference.py --check
cd website
npm ci
npm run build
```

### 4. Docusaurus CI and GitHub Pages deployment

Scope:

- Add Node caching and Docusaurus build checks to docs CI.
- Switch the Pages artifact path from MkDocs `site` to Docusaurus `website/build`.
- Keep release workflows stable until the deployed site is verified.

Dependencies:

- Complete Docusaurus content migration.

Acceptance criteria:

- Pull requests build Docusaurus in CI.
- Pushes to `main` deploy Docusaurus to `https://pooriat.github.io/oterminus/`.
- Important old URLs either still resolve or have documented redirects/rewrites.
- The generated reference pages on the deployed site match current command registry output.

Validation commands:

```bash
poetry run python scripts/check_docs_links.py
poetry run python scripts/generate_command_reference.py --check
cd website
npm ci
npm run build
```

After merge, verify:

```text
https://pooriat.github.io/oterminus/
```

### 5. MkDocs cleanup

Scope:

- Remove MkDocs dependencies from the Poetry docs group.
- Remove `mkdocs.yml` and MkDocs-only assets such as `docs/assets/javascripts/mermaid-fallback.js`
  if no longer used.
- Update CI, docs workflow, TestPyPI workflow, PyPI workflow, contributor docs, release docs, and
  README instructions to use Docusaurus validation.
- Stop generating reference docs under `docs/reference/`.

Dependencies:

- Verified Docusaurus deployment.

Acceptance criteria:

- No workflow runs `poetry run mkdocs build --strict`.
- No contributor or release docs instruct maintainers to validate MkDocs.
- Generated reference docs target `website/docs/reference/`.
- The old `docs/` tree is removed or clearly retained only for non-site source docs.
- GitHub Pages continues to serve `https://pooriat.github.io/oterminus/`.

Validation commands:

```bash
poetry run pytest
poetry run ruff check .
poetry run ruff format --check .
poetry run python scripts/check_docs_links.py
poetry run python scripts/generate_command_reference.py --check
cd website
npm ci
npm run build
```

## Final Cleanup Criteria

MkDocs can be removed only when all of the following are true:

- Docusaurus is deployed successfully from GitHub Actions to the existing Pages URL.
- The Docusaurus sidebar covers every retained page from the old MkDocs nav.
- The request lifecycle Mermaid diagram renders correctly without the MkDocs fallback script.
- Generated command reference docs are produced and checked under the Docusaurus docs root.
- Link checking covers README, Docusaurus docs, generated docs, and sidebar targets.
- Release workflows no longer depend on MkDocs.
- Contributor and release docs no longer mention `poetry run mkdocs build --strict`.
- The old `docs/reference/` generated output is no longer required by any workflow.
- Important README and docs inbound links are preserved, redirected, or intentionally updated.
