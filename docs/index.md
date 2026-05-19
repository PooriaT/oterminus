# OTerminus Documentation Handbook

OTerminus is a local AI terminal assistant that is **capability-first**, **structured-first**, and
**safety-first**. This handbook is the source of truth for product usage, architecture, and
contributor reference material.

## Recommended reading paths

### I want to use OTerminus

1. [What is OTerminus?](product/what-is-oterminus.md)
2. [User guide](product/user-guide.md) — REPL, one-shot, doctor, dry-run, explain, and
   ambiguity handling
3. [Supported workflows](product/supported-workflows.md)
4. [Policy modes](product/policy-modes.md)

### I want to understand the architecture

1. [Architecture overview](architecture/overview.md)
2. [Request lifecycle](architecture/request-lifecycle.md) — direct-command detection, ambiguity
   handling, planning, validation, and execution
3. [Routing and planning](architecture/routing-and-planning.md)
4. [Structured rendering and proposal modes](architecture/structured-rendering.md)
5. [Validation and policy](architecture/validation-and-policy.md)
6. [Execution](architecture/execution.md)

### I want to contribute changes

1. [Contributor workflow](contributing.md)
2. [Capability system](architecture/capability-system.md)
3. [Command registry](architecture/command-registry.md)
4. [Capability map](reference/capability-map.md)
5. [Command families reference](reference/command-families.md)
6. [Adding command families safely](adding-command-families.md)

### I want to debug or test behavior

1. [Observability](architecture/observability.md)
2. [Evals](architecture/evals.md)
3. [Configuration reference](reference/config.md)
4. [Audit log schema](reference/audit-log-schema.md)

## Sections

- Product docs: [`docs/product/`](product/)
- Architecture docs: [`docs/architecture/`](architecture/)
- Reference docs: [`docs/reference/`](reference/)
- ADRs: [`docs/adr/`](adr/)

## Build and preview docs locally

```bash
poetry install --with dev,docs
poetry run mkdocs serve
poetry run mkdocs build --strict
```

See the [contributor workflow](contributing.md) for the complete local lint, format, test, and docs
checklist.

## Documentation contributor notes

When architecture, behavior, configuration, command support, or eval behavior changes, update docs
in the same PR. Keep proposal-mode docs consistent across README and `docs/`: structured and
experimental are the only supported first-class modes.

Before opening a PR, run `poetry run mkdocs build --strict` and fix any warnings or broken links.

Command capability reference pages are generated from the registry; run `poetry run python scripts/generate_command_reference.py --write` after command-spec changes and verify with `--check` before opening a PR.

Keep docs free of secrets, real tokens, personal local paths, or audit logs.

## GitHub Pages setup note

After merging this setup, enable Pages deployment in the repository: **Settings → Pages → Build and
deployment → Source → GitHub Actions**.
