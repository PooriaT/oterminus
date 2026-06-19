# OTerminus

OTerminus is a local, safety-first terminal assistant. It turns natural-language requests into a
**single proposed shell action**, shows a preview, and by default executes only after explicit
confirmation.

## Why OTerminus exists

Terminal copilots are useful, but unrestricted shell generation is risky. OTerminus exists to
provide a practical middle ground:

- capability-first command support (curated workflows, not full shell emulation)
- deterministic rendering for structured command families
- explicit policy + validation gates before execution
- confirmation before execution by default, with an opt-in narrow exception for validated local
  read-only structured commands
- local-first observability through JSONL audit logs

## Core safety promise

OTerminus is designed around an inspect-and-confirm execution contract:

1. detect direct commands first
2. intercept vague natural-language requests as ambiguous when needed
3. route specific natural-language requests by capability
4. plan proposals in a structured-first format
5. validate and policy-check the command
6. show a deterministic preview
7. require explicit user confirmation before execution by default

Direct shell commands are not blocked by natural-language ambiguity heuristics; they still go through
validation and policy checks. Ambiguous natural-language requests stop before planning and execution
and suggest safer read-only inspections. See the [user guide](docs/product/user-guide.md) and
[request lifecycle](docs/architecture/request-lifecycle.md) for details.

If ambiguity handling, validation, or policy checks block a request, OTerminus does not execute.

Users may explicitly enable a narrowly constrained safe auto-execute policy for validated,
warning-free, local read-only structured commands:

```bash
export OTERMINUS_AUTO_EXECUTE_SAFE=true
```

Alternatively, put `OTERMINUS_AUTO_EXECUTE_SAFE=true` in a `.env` file in the directory where you
start OTerminus. Exported shell variables override `.env` values.

The preview, validator, and policy checks still run first. Only direct-command detection and the
deterministic local planner can qualify. Network commands, warnings, write/dangerous risk,
experimental proposals, Ollama-planned proposals, project-health commands, archive extraction or
creation, and history reruns still require confirmation.

## Quick install and setup

### Requirements

- Python 3.13+
- macOS or a Unix-like POSIX terminal environment with the required shell commands available
- [Ollama](https://ollama.com/) for natural-language planning
- [pipx](https://pipx.pypa.io/) for isolated end-user installs
- [Poetry](https://python-poetry.org/) for local development

### Supported platforms

OTerminus currently targets macOS and Unix-like terminal environments. The command registry contains
platform-aware packs: macOS desktop commands such as `open` are available only on supported macOS
(`darwin`) systems, hidden from suggestions and planner context where practical elsewhere, and still
rejected by the validator before execution if requested on an unsupported platform.

Linux-like environments may work when the required shell commands and Ollama are installed, but
OTerminus does not yet claim native Windows Command Prompt or PowerShell support. Windows users
should run OTerminus inside WSL for a Unix-like shell boundary; no Windows command support is added
or implied. Run `oterminus doctor` after installation to see the detected platform and readiness
checks.

### Install from PyPI

Released OTerminus packages are published as `oterminus` and expose the `oterminus` and
`oterminus-evals` console scripts. For normal CLI use, prefer `pipx` because it isolates OTerminus
and its dependencies from your system Python environment:

```bash
pipx install oterminus
oterminus --version
oterminus doctor
oterminus
```

Use `oterminus --version` after install or upgrade to confirm the installed package version. Use
`oterminus doctor` after installation to check the package/runtime environment, pipx or virtualenv
context, platform, configuration files, audit/history paths, and Ollama readiness before your first
natural-language planning request. PyPI installation does not install or start an Ollama model for
you. Direct commands and some deterministic local paths may not need a live model, but first-run
natural-language usage depends on Ollama being installed, running, and having a local model
available.

On the first bare interactive launch (`oterminus`) with no existing user config file, OTerminus
offers a concise configuration wizard. The wizard sets safety/privacy defaults and can select an
installed Ollama model, but model selection is optional and direct commands remain usable without
Ollama. One-shot requests such as `oterminus "ls -l"`, `--dry-run`, `--explain`, `doctor`,
`version`, `completion`, and `config` commands do not trigger onboarding.

Upgrade or uninstall the isolated CLI with:

```bash
pipx upgrade oterminus
pipx uninstall oterminus
```

If you cannot use `pipx`, install with pip instead:

```bash
python -m pip install oterminus
```

### Shell completion vs. REPL autocomplete

OTerminus provides **REPL Tab autocomplete** through `prompt_toolkit` after you start the
interactive app with `oterminus`. It can also print opt-in shell-level completion scripts for the
outer command:

```bash
oterminus completion zsh
oterminus completion bash
oterminus completion fish
```

The completion command only prints the script to stdout; it never edits your `.zshrc`, `.bashrc`,
`config.fish`, or other shell startup files automatically. See the
[shell completion docs](docs/product/shell-completion.md) for manual setup details.

### Configuration management

Use the `oterminus config` namespace to inspect and manage local preferences:

```bash
oterminus config
oterminus config path
oterminus config show
oterminus config get color_mode
oterminus config set color_mode never
oterminus config reset color_mode
oterminus config reset --all-safe
oterminus config init
oterminus config init --defaults
oterminus config validate
oterminus config edit
```

These commands do not require Ollama and bypass request planning, validation, execution, audit, and
history. `oterminus config path` prints the active JSON config path selected by
`OTERMINUS_CONFIG_PATH`, current-directory `.env`, or the default `~/.oterminus/config.json`.
`oterminus config init` runs the interactive onboarding wizard when stdin is a TTY. Use
`oterminus config init --defaults` for non-interactive safe defaults, and
`oterminus config init --defaults --force` to replace an existing valid file. `config edit` uses
`$VISUAL`, then `$EDITOR`, and never modifies shell startup files. The namespace is intentionally
`oterminus config`, not `oterminus --config`, so `--config` remains available for a future
alternate-path option.

Use `oterminus config get <key>`, `oterminus config set <key> <value>`, and
`oterminus config reset <key>` for safe single-setting changes. Supported keys are `model`,
`command_profile`, `auto_execute_safe`, `audit_enabled`, `audit_redact`, `history_enabled`,
`history_redact`, `explain_failures`, `color_mode`, `timeout_seconds`, and `max_output_chars`.
`config reset --all-safe` removes persisted values for exactly that same safe set. Reset removes
values from the user config so effective values fall back through environment, `.env`, and defaults;
it does not delete the config file or edit exported environment variables, `.env`, or shell startup
files. Environment or `.env` values may still override the effective value, and dangerous execution
remains environment-only via `OTERMINUS_ALLOW_DANGEROUS`.

Terminal color policy is configurable with `OTERMINUS_COLOR=auto|always|never` or persisted
`color_mode`:

```bash
export OTERMINUS_COLOR=auto
export OTERMINUS_COLOR=always
export OTERMINUS_COLOR=never
NO_COLOR=1 oterminus
```

Colors are semantic and supplementary: previews, diagnostics, discovery/help output, lifecycle
messages, and the REPL prompt keep visible labels even without color. `auto` disables styling when
output is redirected, and `NO_COLOR` disables ANSI styling at render time. Command stdout/stderr,
version output, shell completion scripts, `config path`, audit/history records, and JSON or other
machine-oriented output remain plain.

### Local development install

```bash
poetry install
poetry run oterminus
```

## Quick start examples

### Common commands

```bash
oterminus
oterminus "show disk usage for this folder"
oterminus --dry-run "copy notes.txt to backup/notes.txt"
oterminus --explain "find processes matching python"
oterminus doctor
oterminus config show
```

### Interactive REPL

`oterminus` starts the interactive REPL. On a first interactive launch without a config file it may
offer onboarding first, then reload the saved config before creating REPL services. Ollama setup is
lazy: it is needed only when a request reaches model-based planning or failure explanation. Use
`poetry run oterminus` when working from a local development checkout.

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

- One-shot requests such as `oterminus "show disk usage for this folder"` plan, validate,
  preview, and then require confirmation before execution unless the explicit safe auto-execute
  environment setting is enabled and the validated proposal qualifies.
- `--dry-run` and `--explain` are mutually exclusive one-shot inspection flags for requests. Both
  validate and preview without confirmation or execution; explain mode also describes command choice,
  relevant flags/arguments, risk, and policy interpretation.
- `--version` prints the installed package version and exits. It does not start the REPL, run
  doctor/setup checks, or require Ollama; `oterminus version` prints the same diagnostic output.
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

Capability maturity/status comes from registry metadata. Planned or metadata-only capabilities are
shown in detailed references/help with warnings, but are not advertised as normal executable
autocomplete or planner actions until their maturity metadata is updated.

See [structured rendering](docs/architecture/structured-rendering.md), [routing and
planning](docs/architecture/routing-and-planning.md), and the [request
lifecycle](docs/architecture/request-lifecycle.md) for details.

## Network diagnostics

The `network_diagnostics` capability supports only fixed-count ping, HTTP HEAD (`curl -I`), `dig`,
and `nslookup`. These commands contact external hosts, show a network metadata warning in preview,
and still require confirmation. OTerminus does not support POST/PUT/DELETE requests, secret headers,
downloads, scanning, SSH, or arbitrary network automation.

## Project health

The `project_health` capability supports curated developer checks through structured operations:
tests, lint checks, format checks, docs builds, and evals. These render to exact `poetry run ...`
commands, may execute local project code, and always go through preview, validation, policy, and
confirmation. OTerminus does not support arbitrary Poetry commands, installs/updates,
deploy/publish commands, or write-formatting such as `ruff format .`.

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
- Dogfooding playbook: [`docs/dogfooding-playbook.md`](docs/dogfooding-playbook.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Release process: [`docs/release.md`](docs/release.md)
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
- Audit logs and persistent history are local JSONL files; redaction is enabled by default, but review logs/history before sharing. See the [audit schema](docs/reference/audit-log-schema.md) and [configuration reference](docs/reference/config.md).

For a small set of deterministic natural-language inspection requests, OTerminus can skip Ollama by
producing a local structured proposal before normal validation and confirmation policy. Examples
include `show hidden files`, `show first 20 lines of README.md`, `search TODO in src`,
`find python processes`, and `show current branch`.
