# oterminus

`oterminus` is a local AI-powered terminal assistant that turns natural-language requests into **proposed** shell commands, then requires explicit user confirmation before execution.
If the input already looks like a shell command, `oterminus` skips the LLM automatically and runs the local validation/execution path directly.

It is intentionally constrained to terminal and local filesystem workflows. The model never gets execution authority.

## Design philosophy

- **Control stays in Python**: Ollama only proposes structured actions.
- **Safety-first**: validation and policy checks run before any command execution.
- **Preview-before-run**: users see summary, exact command, risk level, and warnings first.
- **Extensible architecture**: planner, validator, renderer, policies, and executor are separate modules.

## Architecture (v1)

1. CLI receives input (one-shot or REPL).
2. If the input already looks like a shell command such as `ls -lh` or `cd src`, `oterminus` builds the proposal locally and skips the planner.
3. Otherwise, the planner sends system + user prompt to Ollama.
4. Ollama returns JSON proposal for one shell command.
5. Validator checks structure, allowlist, shell hazards, and policy compatibility.
6. Renderer shows clear command preview.
7. User explicitly confirms.
8. Executor runs the command and returns output + exit code.

## Safety model

Risk levels:

- `safe`: read-only/inspection (`ls`, `pwd`, `find`, `grep`, `du`, etc.)
- `write`: local modifications (`mkdir`, `mv`, `cp`, `chmod`, `touch`)
- `dangerous`: destructive/privileged/high-risk (`rm`, `sudo`, `chown`, broad perms)

Policy controls:

- `OTERMINUS_POLICY_MODE`: `safe`, `write`, or `dangerous`
- `OTERMINUS_ALLOW_DANGEROUS`: `true/false`
- Optional `OTERMINUS_ALLOWED_ROOTS` to scope path targets

Dangerous commands require stronger confirmation (`EXECUTE`).

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/)

## Setup (Poetry)

```bash
poetry install
```

Use either:

```bash
poetry shell
oterminus
```

or:

```bash
poetry run oterminus
```

## Build and install as a global OS command

The package is already configured with a console entry point in `pyproject.toml`:

- `oterminus = "oterminus.cli:main"`

That means when you install the built wheel, your OS gets a globally accessible `oterminus` command on `PATH`.

### 1) Build distributable artifacts

```bash
poetry build
```

This creates:

- `dist/*.whl` (wheel)
- `dist/*.tar.gz` (source distribution)

### 2) Install globally

Recommended (isolated, cross-platform):

```bash
pipx install dist/*.whl
```

Alternative (system/user Python):

```bash
pip install --user dist/*.whl
```

If your shell cannot find `oterminus`, ensure your user scripts/bin directory is on `PATH`:

- Linux/macOS (commonly): `~/.local/bin`
- Windows (commonly): `%APPDATA%\Python\PythonXY\Scripts`

### 3) Verify command availability

```bash
oterminus --help
```

### 4) Upgrade after code changes

```bash
poetry build
pipx install --force dist/*.whl
```

(or reinstall with `pip install --user --upgrade dist/*.whl`)

## Ollama setup

Start Ollama locally, then pull the default model:

```bash
ollama serve
ollama pull gemma4
```

Default model is `gemma4` and can be changed with:

```bash
export OTERMINUS_MODEL=<your_model>
```

## Usage

### Interactive REPL

```bash
poetry run oterminus
```

Commands in REPL:

- `help`: usage tip
- `exit` / `quit`: leave REPL
- direct shell commands like `ls -lh` or `cd src`: validated locally and executed without using Ollama

### One-shot mode

```bash
poetry run oterminus "show me all files in this directory with their sizes"
poetry run oterminus "make run.sh executable"
poetry run oterminus "create a folder called backup"
poetry run oterminus "find all .py files under this directory"
poetry run oterminus "ls -lh"
```

In REPL mode, `cd` updates the `oterminus` process working directory so later natural-language requests run relative to the new location.
In one-shot mode, `cd` only affects that single `oterminus` process and cannot change the parent shell directory.

## Environment variables

- `OTERMINUS_MODEL` (default: `gemma4`)
- `OTERMINUS_TIMEOUT_SECONDS` (default: `60`)
- `OTERMINUS_POLICY_MODE` (default: `write`)
- `OTERMINUS_ALLOW_DANGEROUS` (default: `false`)
- `OTERMINUS_ALLOWED_ROOTS` (colon-delimited list of absolute paths)

## Testing

```bash
poetry run pytest
```

Most tests do not require Ollama running.

## Limitations (v1)

- Curated command allowlist for safety (not arbitrary shell).
- Single command proposals only; no pipelines/chaining.
- No remote/system integrations.
- Not a general-purpose chatbot.

## Future ideas

- richer policy packs by environment
- command templating and explainability improvements
- structured file actions beyond plain shell commands
- shell-specific compatibility layers
