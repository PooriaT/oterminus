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

## Deploy / runtime setup

Start Ollama locally and pull the default model:

```bash
ollama serve
ollama pull gemma4
```

When `oterminus` starts, it first checks that Ollama is installed. If it is, `oterminus` runs `ollama list`, shows the locally installed models, and asks you to select one before continuing.

If Ollama is not installed, or if no models are installed, `oterminus` prints a message and exits. Install Ollama and pull a model first, for example:

```bash
ollama pull gemma4
```
