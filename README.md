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

1. detect direct commands first
2. intercept vague natural-language requests as ambiguous when needed
3. route specific natural-language requests by capability
4. plan proposals in a structured-first format
5. validate and policy-check the command
6. show a deterministic preview
7. require explicit user confirmation before execution

Direct shell commands are not blocked by natural-language ambiguity heuristics; they still go through
validation and policy checks. Ambiguous natural-language requests stop before planning and execution
and suggest safer read-only inspections. See the [user guide](docs/product/user-guide.md) and
[request lifecycle](docs/architecture/request-lifecycle.md) for details.

If ambiguity handling, validation, or policy checks block a request, OTerminus does not execute.

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

## Quick start examples

### Common commands

```bash
poetry run oterminus
poetry run oterminus "show disk usage for this folder"
poetry run oterminus --dry-run "copy notes.txt to backup/notes.txt"
poetry run oterminus --explain "find processes matching python"
poetry run oterminus doctor
```

### Interactive REPL

`poetry run oterminus` starts the interactive REPL after startup readiness checks.

Examples inside REPL:

- `find all .py files`
- `capabilities` / `commands` / `examples`
- `help capabilities` / `help filesystem_inspection` / `help ls`
- `show running processes`
- `ping example.com 4 times`
- `show HTTP headers for https://example.com`
- `look up DNS for example.com`
- `tar -tf archive.tar` / `unzip -l archive.zip`
- `tar -xf archive.tar -C restored` / `unzip archive.zip -d restored`
- `tar -czf backup.tar.gz src` / `zip -r docs.zip docs`
- `ls -lah`
- `dry-run search TODO in src`
- `explain show disk space`
- `audit status` / `audit tail` / `audit clear`

### One-shot and diagnostics modes

- One-shot requests such as `poetry run oterminus "show disk usage for this folder"` plan, validate,
  preview, and then require confirmation before execution.
- `--dry-run` and `--explain` are mutually exclusive one-shot inspection flags for requests. Both
  validate and preview without confirmation or execution; explain mode also describes command choice,
  relevant flags/arguments, risk, and policy interpretation.
- `doctor` is diagnostics-only: it prints readiness checks and exits without starting the REPL,
  executing a request, or invoking the Ollama planner. It cannot be combined with `--dry-run` or
  `--explain`.

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

## Network diagnostics

The `network_diagnostics` capability supports only fixed-count ping, HTTP HEAD (`curl -I`), `dig`,
and `nslookup`. These commands contact external hosts, show a network metadata warning in preview,
and still require confirmation. OTerminus does not support POST/PUT/DELETE requests, secret headers,
downloads, scanning, SSH, or arbitrary network automation.

## Documentation

The README is the landing page. Full documentation is generated from [`docs/`](docs/index.md) and
published to GitHub Pages after merges to `main` (once Pages is enabled in repository settings).

- Hosted docs (after enablement): `https://pooriat.github.io/oterminus/`
- Docs source of truth: [`docs/`](docs/index.md)
- Architecture overview: [`docs/architecture/overview.md`](docs/architecture/overview.md)
- Request lifecycle (central flow):
  [`docs/architecture/request-lifecycle.md`](docs/architecture/request-lifecycle.md)
- User guide: [`docs/product/user-guide.md`](docs/product/user-guide.md)
- Configuration reference: [`docs/reference/config.md`](docs/reference/config.md)
- Contributor workflow: [`docs/contributing.md`](docs/contributing.md)
- Contributor command-family guide:
  [`docs/adding-command-families.md`](docs/adding-command-families.md)
- Evals docs: [`docs/architecture/evals.md`](docs/architecture/evals.md)

### Work on docs locally

```bash
poetry install --with dev,docs
poetry run mkdocs serve
poetry run mkdocs build --strict
```

For the full local quality checklist, including Ruff format/lint and pytest commands, see the
[contributor workflow](docs/contributing.md). When behavior changes, update docs in the same pull
request.

- Optional local persistent REPL history is available via `OTERMINUS_HISTORY_ENABLED=true`; reruns still go through normal validation + confirmation.
