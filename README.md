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
- **Structured-first planning for a curated subset**: the planner should prefer structured proposals for stable command families such as `ls`, `pwd`, `mkdir`, `chmod`, `find`, `cp`, `mv`, `du`, `stat`, `head`, `tail`, `grep`, `cat`, `open`, and `file`, with Python rendering the exact argv/command strings deterministically from `command_family + arguments`.
- **Experimental lane is explicit, not implicit**: proposals that fall outside the deterministic subset can be surfaced as experimental, with stricter validation and stronger confirmation instead of quietly broadening shell access.

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

There are now two supported proposal modes:

- `structured`: preferred and authoritative path; deterministic rendering from validated `command_family` + `arguments`
- `experimental`: explicit raw-shell fallback for planner proposals that do not fit the structured subset but still stay inside the curated allowlist and validator

Legacy `raw` input is accepted only for backward compatibility and is normalized to `experimental` during parsing.
For structured proposals, the raw `command` field is deprecated compatibility metadata and is not used as the execution source of truth.

## Safety model

Risk levels:

- `safe`: read-only/inspection (`ls`, `pwd`, `find`, `grep`, `du`, `stat`, `head`, `tail`, `cat`, `open`, `file`, etc.)
- `write`: local modifications (`mkdir`, `mv`, `cp`, `chmod`, `touch`)
- `dangerous`: destructive/privileged/high-risk (`rm`, `sudo`, `chown`, broad perms)

Command support is registry-driven in `src/oterminus/command_registry.py`, which keeps supported command families, risk metadata, and direct-command support in one place.
Structured rendering lives in `src/oterminus/structured_commands.py` and is intentionally limited to curated, predictable argument shapes for the supported families. Experimental mode still exists for supported variants that are not yet worth structuring.

Policy controls:

- `OTERMINUS_POLICY_MODE`: `safe`, `write`, or `dangerous`
- `OTERMINUS_ALLOW_DANGEROUS`: `true/false`
- Optional `OTERMINUS_ALLOWED_ROOTS` to scope path targets

Dangerous commands require stronger confirmation (`EXECUTE`).
Experimental proposals require a stronger, separate confirmation phrase (`EXECUTE EXPERIMENTAL`) even when their risk level is only `safe` or `write`.

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

The planner may return:

- a structured proposal with `mode: "structured"`, `command_family`, and `arguments`
- an experimental raw proposal with `mode: "experimental"` and a `command` string

Planner behavior is intentionally structured-first:

- if a request cleanly maps to a supported structured family, the planner should emit `mode: "structured"`
- if a request stays within the curated allowlist but does not fit the structured schema, the planner should emit `mode: "experimental"`
- parser normalization upgrades simple command strings (including legacy `mode: "raw"` payloads) into deterministic structured rendering when possible
- legacy `mode: "raw"` payloads that cannot be structured are normalized to `mode: "experimental"` with a deprecation note

When a structured proposal uses one of the supported families, Python validates the argument shape and renders the exact command locally. If a legacy raw `command` string is also present, it is ignored for execution and may be surfaced as a warning when it differs from deterministic rendering.

Supported structured families and argument shapes:

- `ls`: `path`, `long`, `human_readable`, `all`, `recursive`
- `pwd`: no arguments
- `mkdir`: `path`, `parents`
- `chmod`: `path`, `mode` (numeric only, such as `755`)
- `find`: `path`, `name`
- `cp`: `source`, `destination`, `recursive`, `preserve`, `no_clobber`
- `mv`: `source`, `destination`, `no_clobber`
- `du`: `path`, `human_readable`, `summarize`, `max_depth`
- `stat`: `path`, `dereference`, `verbose`
- `head`: `paths`, `lines`, `bytes`
- `tail`: `paths`, `lines`, `bytes`
- `grep`: `pattern`, `paths`, `ignore_case`, `line_number`, `fixed_strings`, `recursive`, `files_with_matches`, `max_count`
- `cat`: `paths`
- `open`: `path`, `reveal`
- `file`: `paths`, `brief`

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

Structured support is intentionally narrow in this step. Pipelines, redirection, multi-command execution, and additional command families are still blocked by validation; experimental mode is a stricter fallback lane for single curated commands, not an unrestricted shell escape hatch.

Examples of newly supported structured intents:

```bash
poetry run oterminus "copy notes.txt to archive/notes.txt without overwriting"
poetry run oterminus "show disk usage summary for this folder in human-readable form"
poetry run oterminus "show the first 20 lines of README.md"
poetry run oterminus "search recursively for TODO in src with line numbers"
poetry run oterminus "open the current folder in Finder"
poetry run oterminus "identify the file type of README.md"
```

## Experimental mode

`experimental` mode exists for requests that do not fit the supported structured families but still map to a single curated command that Python can validate.

What makes it distinct:

- CLI preview labels the proposal as experimental
- preview shows mode, risk level, experimental status, warnings, and confirmation strength
- confirmation is stronger than normal execution and requires `EXECUTE EXPERIMENTAL`
- validator still applies the command allowlist, risk policy, and allowed-root checks
- experimental proposals are rejected if deterministic structured rendering was actually available

Current hard limits in experimental mode:

- no pipelines
- no redirection
- no command chaining
- no background execution
- no command substitution
- no multiline command text
- no obviously dangerous shell metacharacter paths around those constructs
- experimental raw-command validation is still registry-driven, including supported-flag checks and operand-count checks
- `open` is limited to local targets; URL-style operands are rejected

Experimental mode is intentionally stricter, not looser. It broadens proposal coverage a bit without turning `oterminus` into a general shell agent.

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
- Single command proposals only; no pipelines/chaining/redirection/background execution/command substitution.
- Structured rendering is intentionally curated rather than exhaustive; each family only exposes a narrow, deterministic argument shape.
- Experimental mode is still limited to the same curated base-command registry and stronger confirmation.
- No remote/system integrations.
- Not a general-purpose chatbot.

## Future ideas

- richer policy packs by environment
- command templating and explainability improvements
- structured file actions beyond plain shell commands
- shell-specific compatibility layers
