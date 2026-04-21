# oterminus

`oterminus` is a local terminal assistant that converts natural-language requests into a single proposed shell action, previews that action, and runs it only after explicit user confirmation.

It is built for local command-line and filesystem workflows with a safety-first flow:

- one action at a time
- validation before execution
- preview before execution
- explicit confirmation before execution

## Planning architecture (high level)

Natural-language requests now go through a lightweight deterministic capability router before detailed model planning:

1. direct command detection (`ls -lh`, `cd src`, etc.)
2. capability routing (broad family classification)
3. planner proposal generation (structured-first, with route context)
4. validation / policy checks
5. user confirmation and execution

Current routing buckets:

- `filesystem_inspect`
- `filesystem_mutate`
- `text_search`
- `metadata_inspect`
- `process_inspect`
- `unsupported`

The router is intentionally simple and rule-based in v1. It improves family selection hints for planning, but does not replace validator safety checks.

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/)

## Configuration

Configure behavior using environment variables:

- `OTERMINUS_TIMEOUT_SECONDS` (default: `60`)
- `OTERMINUS_POLICY_MODE` (`safe`, `write`, `dangerous`; default: `write`)
- `OTERMINUS_ALLOW_DANGEROUS` (`true`/`false`; default: `false`)
- `OTERMINUS_ALLOWED_ROOTS` (colon-separated absolute paths; optional)

Example:

```bash
export OTERMINUS_POLICY_MODE=write
export OTERMINUS_ALLOW_DANGEROUS=false
export OTERMINUS_ALLOWED_ROOTS=/workspace:/tmp/safe-area
```

## Install (local development)

Install dependencies:

```bash
poetry install
```

Run:

```bash
poetry run oterminus
```

## Install (global command)

Build package artifacts:

```bash
poetry build
```

Install globally (recommended):

```bash
pipx install dist/*.whl
```

Alternative:

```bash
pip install --user dist/*.whl
```

Verify installation:

```bash
oterminus --help
```

Upgrade after changes:

```bash
poetry build
pipx install --force dist/*.whl
```

## First Run & Setup

`oterminus` depends on Ollama and a local model.

On startup, `oterminus` validates prerequisites in this order:

1. Ollama CLI is installed (`ollama` is on `PATH`).
2. Ollama service is running (start with `ollama serve`).
3. At least one local model exists (`ollama list`).

If any prerequisite is missing, `oterminus` prints a clear message and exits.

### First run behavior

If models are available and no model is configured yet, `oterminus` shows a numbered model list and asks you to choose one. The selected model is saved and reused automatically on later runs.

If the saved model is later removed from Ollama, `oterminus` warns you and asks you to select again.

### Config location

Persistent user config is stored at:

- `~/.oterminus/config.json`
- or `OTERMINUS_CONFIG_PATH` when set

Example Ollama setup:

```bash
ollama serve
ollama pull gemma4
```

## Regression evals (golden fixtures)

`oterminus` includes a deterministic evaluation harness for regression protection. Evals run a stable set of natural-language requests through direct-command detection, planner payload parsing, and validation, then compare results against expected outcomes.

This helps catch unintended behavior changes in:

- mode selection (`structured` vs `experimental`)
- command family classification
- risk scoring and policy blocking
- rendered command / argv outputs

### Run evals locally

```bash
poetry run oterminus-evals
```

You can also point to a custom fixture directory:

```bash
poetry run oterminus-evals --fixtures-dir evals/cases
```

Fixtures live under `evals/cases/*.json` and are designed to be extended as new command families or validator rules are added.
