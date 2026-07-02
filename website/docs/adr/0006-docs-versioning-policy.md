---
parse_number_prefixes: false
---

# ADR 0006: Docs versioning policy

## Status
Accepted

## Context
OTerminus publishes a Docusaurus site from `website/` using Docusaurus 3.10.x. The docs plugin is
mounted at the site root with `routeBasePath: '/'`, so versioning would need an intentional route and
navigation plan instead of assuming Docusaurus's default `/docs` URLs.

The project is still a pre-1.0 Python CLI package (`0.1.x`, alpha). Its docs currently track the
latest code on `main` and include release notes, a release checklist, configuration reference,
capability reference, generated command-family reference, eval guidance, and package validation
workflows. The generated command-family reference is produced from the live command registry, so a
historical docs snapshot would need to preserve generated output for that release rather than
regenerating old docs from newer code.

Official Docusaurus versioning guidance supports snapshotting the current docs into
`versioned_docs/`, `versioned_sidebars/`, and `versions.json` with
`npx docusaurus docs:version <version>`. The same guidance warns that most sites do not need
versioning because it increases build time and codebase complexity, is best suited for high-traffic
projects with rapid docs changes between versions, and should keep the number of active versions
small. It also notes that relative imports and assets can become harder to manage once docs are
versioned.

## Decision
Do not enable Docusaurus docs versioning before OTerminus 1.0.

Keep one latest-only docs site for now, backed by `CHANGELOG.md`, GitHub Releases, PyPI package
versions, and the release guide for historical release context. Revisit Docusaurus versioning only
after stable public releases create meaningful documentation drift or users demonstrably need docs
for older installed versions.

Generated references remain latest-only until versioning is explicitly enabled. If versioning is
enabled later, generated reference files must be snapshotted as part of each docs version and old
versioned docs must not be regenerated from the latest command registry.

## Options considered

### Option A: latest-only docs
Keep one current docs site that tracks `main`.

Pros:

- simplest documentation model;
- lowest maintenance burden for a small project;
- avoids duplicated docs and duplicated sidebars;
- easiest fit for the current generated command-reference workflow;
- appropriate for a pre-1.0 CLI whose public behavior is still settling.

Cons:

- older package versions may not match the latest docs perfectly;
- users reading docs after installing an older version may need the changelog or release notes to
  understand differences.

### Option B: enable Docusaurus versioning per minor or major release
Snapshot docs with:

```bash
cd website
npx docusaurus docs:version <version>
```

Pros:

- users can read docs for older releases;
- useful after stable public adoption when behavior and docs diverge by release;
- aligns historical docs with release-specific CLI behavior if maintained carefully.

Cons:

- duplicates content in `versioned_docs/` and sidebars in `versioned_sidebars/`;
- requires `versions.json` and likely navigation changes such as a version dropdown;
- increases CI and Docusaurus build time;
- requires contributors to know when to update current docs only versus multiple active versions;
- complicates the generated command-reference workflow because historical generated files must stay
  tied to the release they document;
- needs extra care with relative docs links, imports, and assets once files are copied into versioned
  folders;
- interacts with the current root docs route (`routeBasePath: '/'`) and therefore needs a route
  strategy before implementation.

### Option C: lightweight release-note-based version history
Keep latest-only docs, but rely on:

- `CHANGELOG.md`;
- GitHub Releases;
- the release guide;
- PyPI package versions;
- possibly an archive or release-history page later.

Pros:

- good middle ground for pre-1.0 releases;
- low maintenance;
- preserves clear release history without duplicating every docs page;
- avoids Docusaurus versioning complexity until there is evidence it is needed.

Cons:

- not a full historical docs snapshot;
- users on older versions may need to combine latest docs with changelog entries.

## Why not enable versioning now?
OTerminus is still pre-1.0 and alpha. The docs mostly describe the current safety model,
capabilities, install flow, configuration, and generated command references. Maintaining historical
snapshots before stable public adoption would add duplicated content, route decisions, sidebar
management, generated-reference policy, and longer validation work before those costs are justified.

The current release assets already provide lightweight history: `CHANGELOG.md` records user-facing
changes, GitHub Releases can summarize tagged releases, PyPI preserves package versions, and the
release guide defines the validation gates for package publishing. That is enough until users need
older docs for materially different installed versions.

## When should we revisit?
Revisit this decision when one or more of these triggers is true:

- OTerminus reaches `1.0.0`;
- public users depend on older OTerminus versions;
- CLI behavior, policy modes, config shape, or install instructions become incompatible across
  supported releases;
- generated command references diverge significantly by release;
- docs traffic, issues, discussions, or support requests show users need older docs;
- package install or upgrade instructions differ meaningfully by version;
- the project decides to support multiple active release lines.

## What would implementation require?
If versioning becomes worthwhile later, use this checklist before creating any Docusaurus versioning
artifacts:

- confirm the route strategy with the current `routeBasePath: '/'` site-root docs setup;
- choose a version naming policy, preferably major/minor snapshots only;
- decide whether patch releases ever get docs snapshots;
- update `website/docusaurus.config.ts` for the selected versioning behavior;
- add a version dropdown only if it improves navigation;
- run `cd website && npx docusaurus docs:version <version>` when the current docs are ready to
  freeze;
- snapshot generated reference files with each docs version;
- update `scripts/generate_command_reference.py` to either target versioned docs deliberately or stay
  explicitly latest-only;
- update `scripts/check_docs_links.py` for versioned paths and any archive policy;
- update CI, release docs, and release workflows as needed;
- add a release checklist step for docs snapshots;
- decide how many active versions to keep;
- document how older versions are archived or removed from active navigation.

## Consequences
- No `versions.json`, `versioned_docs/`, `versioned_sidebars/`, version dropdown, or versioned
  deployment logic is added now.
- Contributors continue updating the latest docs only.
- Generated command references continue to reflect the current command registry and are checked as
  latest-only docs.
- Release history remains available through changelog entries, release notes, PyPI versions, and the
  release guide.
- The project has explicit triggers and an implementation checklist for adopting versioning later
  without committing to that complexity prematurely.

## Validation
This decision is validated by checking that the docs site still builds and typechecks, generated
command references remain current, docs links are valid, and no Docusaurus versioning artifacts are
created in this PR.
