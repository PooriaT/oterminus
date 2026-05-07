# OTerminus

OTerminus is a local, safety-first terminal assistant. It turns natural-language requests into a
**single proposed shell action**, shows a preview, and executes only after explicit confirmation.

## Why OTerminus exists

Terminal copilots are useful, but unrestricted shell generation is risky. OTerminus exists to
provide a practical middle ground:

- capability-first command support (curated workflows, not full shell emulation)
- deterministic rendering for structured command families
- explicit policy + validation gates before execution
- confirmation before every execution path
- local-first observability through JSONL audit logs

## Core safety promise

OTerminus is designed around an inspect-and-confirm execution contract:

1. detect direct commands and handle ambiguity
2. route requests by capability
3. plan proposals in a structured-first format
4. validate and policy-check the command
5. show a deterministic preview
6. require explicit user confirmation before execution

If validation or policy checks fail, OTerminus does not execute.

## Quick install and setup

### Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/)

### Local development install

```bash
poetry install
poetry run oterminus
```

On first run, OTerminus checks Ollama readiness (`ollama` on PATH, running service, local models),
then prompts you to select a model if one is not already configured.

### Useful startup checks

```bash
poetry run oterminus doctor
```

## Quick start examples

### Interactive REPL

```bash
poetry run oterminus
```

Examples inside REPL:

- `find all .py files`
- `show running processes`
- `ls -lah`
- `dry-run search TODO in src`
- `explain show disk space`

### One-shot mode

```bash
poetry run oterminus "show disk usage for this folder"
poetry run oterminus --dry-run "copy notes.txt to backup/notes.txt"
poetry run oterminus --explain "find processes matching python"
```

## Proposal modes

OTerminus supports two first-class proposal modes:

- **Structured**: the preferred normal path for supported capabilities. Proposals use
  `command_family` + typed `arguments`, and Python renders the final command/argv deterministically.
- **Experimental**: a constrained fallback for single-command text that cannot yet be represented
  safely as structured arguments. It is still strictly validated, previewed, and confirmed before
  execution.

See [structured rendering](docs/architecture/structured-rendering.md), [routing and
planning](docs/architecture/routing-and-planning.md), and the [request
lifecycle](docs/architecture/request-lifecycle.md) for details.

## Documentation

The README is the landing page. Full documentation is generated from [`docs/`](docs/index.md) and
published to GitHub Pages after merges to `main` (once Pages is enabled in repository settings).

- Hosted docs (after enablement): `https://pooriat.github.io/oterminus/`
- Docs source of truth: [`docs/`](docs/index.md)
- Architecture overview: [`docs/architecture/overview.md`](docs/architecture/overview.md)
- Request lifecycle (central flow):
  [`docs/architecture/request-lifecycle.md`](docs/architecture/request-lifecycle.md)
- User guide: [`docs/product/user-guide.md`](docs/product/user-guide.md)
- Contributor workflow: [`docs/contributing.md`](docs/contributing.md)
- Contributor command-family guide:
  [`docs/adding-command-families.md`](docs/adding-command-families.md)
- Evals docs: [`docs/architecture/evals.md`](docs/architecture/evals.md)

### Work on docs locally

```bash
poetry install --with dev
poetry run python -m pip install mkdocs mkdocs-material
poetry run mkdocs serve
poetry run mkdocs build --strict
```

For the full local quality checklist, including Ruff format/lint and pytest commands, see the
[contributor workflow](docs/contributing.md). When behavior changes, update docs in the same pull
request.
