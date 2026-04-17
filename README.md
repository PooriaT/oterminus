# oterminus

`oterminus` is a local terminal assistant that translates natural-language requests into a single **proposed** shell action, previews that action, and executes it only after explicit user confirmation.

The current architecture is **structured-first**:

- Prefer deterministic `structured` proposals (`command_family` + validated `arguments`)
- Use `experimental` only as a constrained fallback for supported single-command cases that are not yet represented by the structured schema
- Keep legacy raw compatibility as a transitional parsing behavior, not as the main execution model

At every stage, Python owns control. The model can suggest; it cannot execute.

## Overview

`oterminus` is designed for local command-line and filesystem workflows. It does **not** operate as a generic autonomous agent:

- It proposes one action at a time
- It validates proposals against a curated command registry and safety checks
- It always shows a preview before run
- It requires user confirmation
- It executes with local Python subprocess logic after checks pass

If user input already looks like a direct shell command (for example, `ls -lh` or `cd src`), `oterminus` can skip model planning and run the same validation/preview/confirmation/execution pipeline locally.

## Design philosophy

1. **Python is the control plane**
   - Planning assistance comes from Ollama, but rendering, validation, policy enforcement, and execution are local Python responsibilities.
2. **Structured proposals are primary**
   - Deterministic rendering from typed arguments is preferred whenever possible.
3. **Safety before execution**
   - Command shape checks, allowlist checks, path controls, risk classification, and policy gating happen before execution.
4. **Single source of truth for command support**
   - `command_registry` defines what command families are supported and how they are interpreted.
5. **Explicit fallback lane**
   - `experimental` is intentional and constrained, with stricter confirmation requirements.

## Current architecture

High-level architecture:

```text
User input
   |
   v
Direct command detection? ----- yes -----> Local Proposal (structured if parseable, else experimental)
   | no
   v
Planner -> Ollama (JSON proposal)
   |
   v
Proposal parsing + mode normalization/preference
   |
   v
Validator (render + command shape + allowlist + safety + policy checks)
   |
   v
Renderer (preview)
   |
   v
User confirmation
   |
   v
Executor (subprocess / built-in cd handling)
```

End-to-end invariants:

- The model never receives execution authority.
- Execution is only performed from validated argv in Python.
- Structured mode rendering is deterministic and local.
- Unsupported or unsafe proposals are rejected before execution.

## Request lifecycle

### 1) User input ingestion

The CLI accepts either:

- one-shot request text (`oterminus "..."`), or
- interactive REPL input (`oterminus` then `oterminus> ...`).

### 2) Direct command detection (when applicable)

Before using the planner, `oterminus` tries to detect whether the request already looks like a direct invocation of a curated command family (for example `ls`, `find`, `grep`, `cd`).

- If direct detection succeeds, it constructs a local `Proposal`.
- It attempts to parse into `structured` mode first.
- If deterministic structured parsing is unavailable, it falls back to `experimental` mode for that single command.

### 3) Planner interaction with Ollama (natural language path)

If direct detection does not match, `Planner.plan()` sends:

- a strict system prompt (JSON-only, single action, curated command families), and
- a user prompt containing the original request.

The Ollama client asks for JSON output (`format="json"`) and returns raw JSON text.

### 4) Proposal creation/parsing

Planner parsing includes:

- JSON decoding,
- pydantic schema validation into `Proposal`,
- proposal mode normalization and structured preference.

Important mode behavior:

- `structured` requires `command_family` + `arguments`.
- `experimental` requires a raw `command` string.
- legacy `mode: "raw"` payloads are normalized to modern modes (transitional compatibility).

### 5) Validation

`Validator.validate()` computes an execution-ready `ValidationResult`:

- Determines risk from registry metadata
- Renders structured proposals into deterministic argv/command
- Parses experimental raw commands safely (`shlex`)
- Rejects shell operators/fragments (pipelines, redirection, chaining, substitution, multiline, etc.)
- Enforces command-specific shape/flag constraints from registry metadata
- Applies forbidden operand checks and optional allowed-root path constraints
- Applies policy-based risk gating

### 6) Rendering / preview

The renderer prints a proposal preview containing:

- summary, explanation, mode, risk level
- command family and arguments (when structured)
- resolved rendered command
- notes, warnings, and rejection reasons
- confirmation strength required

### 7) Confirmation

Confirmation requirements are policy-driven by proposal mode + risk:

- Standard prompt for non-dangerous structured proposals
- Strong `EXECUTE` for dangerous
- Very strong `EXECUTE EXPERIMENTAL` for all experimental proposals

### 8) Execution

Execution happens only after confirmation and only from validated argv.

- Regular commands use `subprocess.run(...)` with timeout.
- `cd` is handled in-process so REPL session state (cwd) is preserved.

## Module guide

- `cli`
  - Entry point, argument parsing, REPL loop, request orchestration, confirmation prompting.
- `planner`
  - Calls Ollama through client, parses JSON, validates schema, prefers structured rendering when possible.
- `prompts`
  - Builds system/user prompts and defines structured-family argument shapes expected from planner output.
- `ollama_client`
  - Thin client wrapper around Ollama chat API with JSON response contract and error normalization.
- `models`
  - Pydantic/domain models (`Proposal`, `ValidationResult`, enums) and mode/schema constraints.
- `command_registry`
  - Curated command support source of truth: risk levels, allowed flags, detection modes, operand rules, path semantics.
- `structured_commands`
  - Typed argument schemas, structured argument validation, deterministic rendering to argv, and raw-to-structured parsing helpers.
- `validator`
  - Central gatekeeper: validates proposal structure, enforces registry constraints, evaluates hazards, computes acceptance/risk/warnings, and returns safe argv.
- `policies`
  - Runtime risk policy (`safe` / `write` / `dangerous`), dangerous-command toggle, confirmation-level calculation.
- `renderer`
  - Human-facing proposal preview formatting.
- `executor`
  - Executes validated argv (or internal `cd`) and returns structured execution result.

## Safety and validation model

Safety is layered, not a single check.

### Core safety properties

- **Curated allowlist:** base command must be present in `command_registry`.
- **Deterministic structured rendering:** in `structured` mode, Python builds final argv.
- **Shell hazard blocking:** rejects chaining, redirection, subshell constructs, etc.
- **Command-shape checks:** flags/operands validated per command spec.
- **Path controls:** optional root scoping with `OTERMINUS_ALLOWED_ROOTS`.
- **Risk gating:** policy can block write/dangerous actions.
- **Human confirmation:** always required, stronger for higher risk and experimental mode.

### Validator vs policy (important distinction)

- **Validator** answers: “Is this proposal technically and structurally acceptable in curated oterminus semantics?”
  - Includes command shape, allowlist membership, hazard checks, path constraints, and rendered argv availability.

- **Policy** answers: “Given a structurally valid proposal, is this risk level allowed right now?”
  - Depends on runtime settings (`mode`, `allow_dangerous`, and roots).

So: validator enforces *what is valid*; policy enforces *what is permitted now*.

## Proposal modes

### `structured` (primary)

Preferred and authoritative mode.

- Requires `command_family` and `arguments`
- Arguments are validated against typed schemas
- Final command is rendered deterministically in Python
- Raw `command` is deprecated compatibility metadata if present and is not execution authority

### `experimental` (constrained fallback)

Used when a request is still a single curated command, but does not fit current structured schemas.

- Requires `command`
- Still constrained by registry/validator checks
- Requires very strong confirmation phrase (`EXECUTE EXPERIMENTAL`)

### Legacy `raw` compatibility (transitional)

Legacy payloads may still appear from older planner behavior. They are normalized during parsing:

- `mode: "raw"` is converted into current modes
- If structured fields exist or raw command can be deterministically parsed, proposal becomes `structured`
- Otherwise it is treated as `experimental`

This compatibility path exists to ease transition and should not be treated as primary architecture.

## Configuration

Environment variables:

- `OTERMINUS_MODEL` (default: `gemma4`)
- `OTERMINUS_TIMEOUT_SECONDS` (default: `60`)
- `OTERMINUS_POLICY_MODE` (`safe`, `write`, `dangerous`; default: `write`)
- `OTERMINUS_ALLOW_DANGEROUS` (`true`/`false`; default: `false`)
- `OTERMINUS_ALLOWED_ROOTS` (colon-separated absolute paths; optional)

Examples:

```bash
export OTERMINUS_MODEL=gemma4
export OTERMINUS_POLICY_MODE=write
export OTERMINUS_ALLOW_DANGEROUS=false
export OTERMINUS_ALLOWED_ROOTS=/workspace:/tmp/safe-area
```

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/)

## Local development

### Setup (Poetry)

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

### Build and install as a global OS command

The package is configured with a console entry point in `pyproject.toml`:

- `oterminus = "oterminus.cli:main"`

That means installing the wheel exposes `oterminus` on `PATH`.

#### 1) Build distributable artifacts

```bash
poetry build
```

This creates:

- `dist/*.whl`
- `dist/*.tar.gz`

#### 2) Install globally

Recommended (isolated, cross-platform):

```bash
pipx install dist/*.whl
```

Alternative:

```bash
pip install --user dist/*.whl
```

If your shell cannot find `oterminus`, ensure your scripts/bin directory is on `PATH`:

- Linux/macOS: commonly `~/.local/bin`
- Windows: commonly `%APPDATA%\Python\PythonXY\Scripts`

#### 3) Verify command availability

```bash
oterminus --help
```

#### 4) Upgrade after code changes

```bash
poetry build
pipx install --force dist/*.whl
```

(or reinstall with `pip install --user --upgrade dist/*.whl`)

### Ollama setup

Start Ollama locally, then pull the default model:

```bash
ollama serve
ollama pull gemma4
```

Use a different model with:

```bash
export OTERMINUS_MODEL=<your_model>
```

### CLI usage

#### Interactive REPL

```bash
poetry run oterminus
```

REPL commands:

- `help`
- `exit` / `quit`
- direct shell commands such as `ls -lh` or `cd src`

In REPL mode, `cd` updates the running process working directory for subsequent requests.
In one-shot mode, `cd` only affects that `oterminus` process.

#### One-shot mode

```bash
poetry run oterminus "show me all files in this directory with their sizes"
poetry run oterminus "make run.sh executable"
poetry run oterminus "create a folder called backup"
poetry run oterminus "find all .py files under this directory"
poetry run oterminus "ls -lh"
```

## Testing

Run all tests:

```bash
poetry run pytest
```

Targeted examples:

```bash
poetry run pytest tests/test_planner_parsing.py
poetry run pytest tests/test_validator.py
poetry run pytest tests/test_structured_commands.py
```

## Limitations / future improvements

Current intentional limitations:

- Single-action proposals only (no multi-step workflows)
- Structured coverage is intentionally narrow and curated
- Experimental mode still allows only constrained single commands
- No unrestricted shell execution, pipelines, or redirection
- Model quality depends on local Ollama model behavior and prompt adherence

Potential future improvements:

- Expand structured schemas to reduce experimental fallback frequency
- Improve cross-platform command-family handling (for non-macOS `open` equivalents)
- Add richer per-command policy controls and audit logging
- Provide clearer UX around policy-denied but structurally-valid proposals
