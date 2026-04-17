# oterminus

`oterminus` is a local AI-powered terminal assistant that turns natural-language requests into **proposed** shell commands, then requires explicit user confirmation before execution.
If the input already looks like a shell command, `oterminus` skips the LLM automatically and runs the local validation/execution path directly.

It is intentionally constrained to terminal and local filesystem workflows. The model never gets execution authority.

## Design philosophy

- **Control stays in Python**: Ollama only proposes actions; Python owns validation, rendering, and execution.
- **Safety-first**: validation and policy checks run before any command execution.
- **Preview-before-run**: users see summary, exact command, risk level, and warnings first.
- **Extensible architecture**: planner, validator, renderer, policies, and executor are separate modules.
- **Registry-driven command support**: a shared command registry defines the curated v1 command set, risk levels, and direct-command eligibility.
- **Deterministic structured rendering for a narrow subset**: `ls`, `pwd`, `mkdir`, `chmod`, and `find` can be represented as structured proposals and rendered into exact argv/command strings by Python.

## Architecture (v1)

1. CLI receives input (one-shot or REPL).
2. If the input already looks like a shell command such as `ls -lh` or `cd src`, `oterminus` builds the proposal locally and skips the planner.
3. Otherwise, the planner sends system + user prompt to Ollama.
4. Ollama returns a JSON proposal for one shell action.
5. Validator checks structure, the registry-backed allowlist, shell hazards, and policy compatibility.
6. For supported structured proposals, Python deterministically renders the final command from `command_family` + `arguments`.
7. Renderer shows clear command preview.
8. User explicitly confirms.
9. Executor runs the resolved argv and returns output + exit code.

Raw-command execution remains in place for everything outside the structured subset.

## Safety model

Risk levels:

- `safe`: read-only/inspection (`ls`, `pwd`, `find`, `grep`, `du`, etc.)
- `write`: local modifications (`mkdir`, `mv`, `cp`, `chmod`, `touch`)
- `dangerous`: destructive/privileged/high-risk (`rm`, `sudo`, `chown`, broad perms)

Command support is registry-driven in `src/oterminus/command_registry.py`, which keeps supported command families, risk metadata, and direct-command support in one place.
Structured rendering lives in `src/oterminus/structured_commands.py` and is intentionally limited to the curated subset listed above.

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

## Structured planning support

The planner may now return either:

- a raw proposal with `mode: "raw"` and a `command` string
- a structured proposal with `mode: "structured"`, `command_family`, and `arguments`

When a structured proposal uses one of the supported families, Python validates the argument shape and renders the exact command locally.

Supported structured families and argument shapes:

- `ls`: `path`, `long`, `human_readable`, `all`, `recursive`
- `pwd`: no arguments
- `mkdir`: `path`, `parents`
- `chmod`: `path`, `mode` (numeric only, such as `755`)
- `find`: `path`, `name`

Example structured proposals:

```json
{
  "action_type": "shell_command",
  "mode": "structured",
  "command_family": "ls",
  "arguments": {
    "path": ".",
    "long": true,
    "human_readable": true,
    "all": false,
    "recursive": false
  },
  "summary": "List files with sizes",
  "explanation": "Use a long listing in the current directory",
  "risk_level": "safe",
  "needs_confirmation": true,
  "notes": []
}
```

```json
{
  "action_type": "shell_command",
  "mode": "structured",
  "command_family": "find",
  "arguments": {
    "path": ".",
    "name": "*.py"
  },
  "summary": "Find Python files",
  "explanation": "Search recursively under the current directory",
  "risk_level": "safe",
  "needs_confirmation": true,
  "notes": []
}
```

Structured support is intentionally narrow in this step. Pipelines, redirection, multi-command execution, and additional command families still require the raw-command path and remain subject to the existing validator.

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
- Structured rendering is limited to `ls`, `pwd`, `mkdir`, `chmod`, and `find`.
- No remote/system integrations.
- Not a general-purpose chatbot.

## Future ideas

- richer policy packs by environment
- command templating and explainability improvements
- structured file actions beyond plain shell commands
- shell-specific compatibility layers
