# oterminus

`oterminus` is a local terminal assistant that converts natural-language requests into a single proposed shell action, previews that action, and runs it only after explicit user confirmation.

It is built for local command-line and filesystem workflows with a safety-first flow:

- one action at a time
- validation before execution
- preview before execution
- explicit confirmation before execution

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
