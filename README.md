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
2. ambiguity guardrails for vague/broad/destructive wording
3. capability routing (broad family classification)
4. planner proposal generation (structured-first, with route context)
5. validation / policy checks
6. user confirmation and execution

Current routing buckets:

- `filesystem_inspect`
- `filesystem_mutate`
- `text_search`
- `metadata_inspect`
- `process_inspect`
- `unsupported`

The router is intentionally simple and rule-based in v1. It uses registry capability metadata (capability IDs, aliases, and command examples) to derive suggested families, which reduces duplicated command-family hints across routing and planning. It improves family selection hints for planning, but does not replace validator safety checks.

## Ambiguous-request handling

Before model planning, OTerminus now checks natural-language requests for ambiguity using deterministic local rules. If a request is broad, underspecified, or potentially destructive (for example, “clean this folder”, “fix this”, “delete unnecessary files”, or “make this project work”), OTerminus does **not** guess and does **not** execute.

Instead, it returns safer inspection options:

- list large files
- list recently modified files
- inspect permissions
- show temporary-looking files
- show project files

This keeps the flow inspect-first:

- Instead of “remove junk files”, inspect candidate files first.
- Instead of “repair permissions”, inspect current permissions first.
- Then provide a narrower follow-up request with exact paths and intended scope.

## Non-execution modes (`--dry-run`, `--explain`)

OTerminus now supports two safe one-shot modes for learning, demos, debugging, and inspection without running shell commands:

- `--dry-run`: runs direct-detection/routing/planning/validation and shows the rendered command preview, but never asks for confirmation and never executes.
- `--explain`: runs the same pipeline and prints a structured explanation of why a command was chosen, risk level, key flags/arguments (when known), and whether policy would allow execution.

Examples:

```bash
oterminus --dry-run "find large files in this folder"
oterminus --explain "show running processes"
oterminus --dry-run "make run.sh executable"
oterminus --explain "search TODO in Python files"
```

In REPL mode, built-ins are available:

- `dry-run <request>`
- `explain <request>`
- `history`
- `history <n>`
- `explain <history_id>`
- `rerun <history_id>`
- `capabilities`
- `commands`
- `examples` / `examples <capability_id>`
- `help capabilities`
- `help <capability_id>`
- `help <command_family>`

Discovery built-ins are local-only REPL UX helpers: they do not call Ollama, do not execute commands, and only read the local command/capability registry metadata.

## REPL session history commands

OTerminus keeps an **in-memory history for the current REPL session only** (v1): nothing is persisted across restarts.

- `history`: show a compact table of recent requests (id, input, command, risk, status)
- `history <n>`: show only the last `n` requests
- `explain <history_id>`: re-render explanation details for a previous request without execution
- `rerun <history_id>`: replays a previous request through the normal pipeline

`rerun` is intentionally safe: it does **not** execute immediately, it re-runs validation against current policy, shows preview again, and requires confirmation again. Previously rejected commands are still rejected unless current policy allows them.

Command metadata for structured command support is maintained in a central merged registry built from modular capability packs under `src/oterminus/commands/` (filesystem, text, process, system, macOS, dangerous). Each command is tagged with a workflow capability (`capability_id`, label, concise description, aliases, examples, maturity), so OTerminus scales by curated user workflows rather than trying to mirror every shell man page.

OTerminus is intentionally **capability-first**, not “all shell commands”:

- `filesystem_inspection`
- `filesystem_mutation`
- `text_inspection`
- `process_inspection`
- `system_inspection`
- `macos_desktop`
- `destructive_operations`

The registry is used to answer both:

- “Is this command allowed?”
- “What capability/workflow does it belong to?”

Planner prompts consume a compact capability summary generated from this same registry metadata, so model context stays concise and does not dump the entire command registry.

Contributor guidance for extending this registry safely is available at [`docs/adding-command-families.md`](docs/adding-command-families.md).

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
- `OTERMINUS_AUDIT_LOG_PATH` (path for local JSONL request audit log; default: `~/.oterminus/audit.jsonl`)
- `OTERMINUS_AUDIT_ENABLED` (`true`/`false`; default: `true`)
- `OTERMINUS_AUDIT_REDACT` (`true`/`false`; default: `true`)

Example:

```bash
export OTERMINUS_POLICY_MODE=write
export OTERMINUS_ALLOW_DANGEROUS=false
export OTERMINUS_ALLOWED_ROOTS=/workspace:/tmp/safe-area
export OTERMINUS_AUDIT_LOG_PATH=~/.oterminus/audit.jsonl
export OTERMINUS_AUDIT_ENABLED=true
export OTERMINUS_AUDIT_REDACT=true
```

## Local observability and debugging

`oterminus` writes a local structured audit record for each handled request lifecycle. This is intentionally lightweight and local-only: there is no external telemetry, analytics backend, or cloud upload.

### Audit log location

- default: `~/.oterminus/audit.jsonl`
- override with `OTERMINUS_AUDIT_LOG_PATH`
- or set `"audit_log_path"` in `~/.oterminus/config.json` (or your `OTERMINUS_CONFIG_PATH` file)

Each line is JSON with fields such as:

- `timestamp`
- `user_input`
- `direct_command_detected`
- `ambiguity_detected`
- `ambiguity_reason`
- `ambiguity_safe_options`
- `routed_category`
- `proposal_mode`
- `command_family`
- `rendered_command`
- `argv`
- `validation_accepted`
- `warnings`
- `rejection_reasons`
- `confirmation_result`
- `execution_exit_code`
- `rerun_source_history_id`
- `duration_ms`

### Audit privacy controls

Audit logs are **local-only** and stay on your machine. OTerminus does not upload audit logs or send telemetry.

- `OTERMINUS_AUDIT_ENABLED=false` disables writing audit log lines entirely.
- `OTERMINUS_AUDIT_REDACT=true` (default) redacts likely secret material in audit fields such as:
  - user input and rendered commands
  - argv values
  - warning and rejection text
- Redaction covers practical patterns like bearer tokens, GitHub tokens, API keys, passwords, secret flags (`--token`, `--password`, `--api-key`), environment-style assignments (`KEY=value`), and URLs with embedded credentials.
- `OTERMINUS_AUDIT_REDACT=false` is an explicit opt-out and logs raw values.

Use `audit status` (one-shot or in REPL) to inspect current audit settings and log path.

### Debug-friendly request trace

Use `--verbose` to enable a concise trace in the terminal showing:

- route decision
- proposal mode/family
- validator summary
- confirmation outcome

This helps diagnose planner/validator disagreements without enabling noisy output during normal runs.

## Install (local development)

Install dependencies:

```bash
poetry install
```

Run:

```bash
poetry run oterminus
```

In interactive REPL mode, `Tab` provides deterministic local autocomplete for built-ins (`help`, `capabilities`, `commands`, `examples`, `history`, `rerun`, `dry-run`, `explain`, `exit`, `quit`), curated command names/categories, and local filesystem paths. Tab completion is local-only and does not call the planner or model.

## Diagnostics: `oterminus doctor`

Use the doctor command to troubleshoot local readiness without entering the assistant REPL or running a planning request:

```bash
oterminus doctor
```

It runs concise PASS/WARN/FAIL checks for:

- Python/runtime compatibility
- package importability
- Ollama CLI/service/models/configured model
- config and audit log path permissions
- autocomplete dependency (`prompt_toolkit`)
- command registry integrity (including duplicate names)
- eval fixture directory and parseability
- optional dev tooling availability (Poetry)

Example output:

```text
oterminus doctor
PASS  python version: Detected 3.13.2.
PASS  oterminus package: Import succeeded.
PASS  ollama CLI: Found on PATH.
WARN  prompt_toolkit: Not installed; REPL autocomplete will be disabled.
      ↳ Install dependencies with `poetry install` to enable autocomplete.
Summary: 13 checks, 0 failed, 1 warnings
```

If critical checks fail, `oterminus doctor` exits non-zero so it can be used in scripts/CI.

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


## Structured command support (deterministic rendering)

`oterminus` uses deterministic rendering for a curated set of command families when possible. In structured mode, the model provides `command_family + arguments`, then Python validates and renders the final argv/command string.

Supported structured families include:

- `ls`, `pwd`, `clear`, `whoami`, `uname`, `which`, `env`
- `find`, `du`, `df`, `stat`, `head`, `tail`, `grep`, `cat`, `file`, `wc`, `sort`, `uniq`
- `ps`, `pgrep`, `lsof`
- `mkdir`, `cp`, `mv`, `chmod`, `open`

Examples of requests that now land in structured mode:

- “copy notes.txt to backup/notes.txt” → `cp notes.txt backup/notes.txt`
- “move report.md into docs” → `mv report.md docs`
- “show disk usage for this folder” → `du .`
- “show metadata for this file” → `stat README.md`
- “show the first 20 lines of README.md” → `head -n 20 README.md`
- “search for TODO in all python files here” → `grep -r TODO *.py`
- “open this folder in Finder” → `open .`
- “tell me what kind of file this is” → `file README.md`
- “show running processes” → `ps -A`
- “find processes matching python” → `pgrep -f python`
- “show open files for this directory” → `lsof .`
- “show disk space” → `df -h` (or `df` for default all filesystems)
- “show current username” → `whoami`
- “show system name” → `uname -s`
- “clear the terminal before a demo” → `clear`
- “find where python is installed” → `which python`
- “count lines in README.md” → `wc -l README.md`
- “sort this file” → `sort README.md`
- “show unique lines in this file” → `uniq README.md`

When a request cannot be represented safely in these deterministic schemas, `oterminus` falls back to `experimental` mode and applies stricter confirmation behavior.

`env` is supported in curated mode only for single-variable lookups (for example `env PATH`) to reduce accidental secret exposure from full environment dumps.

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
