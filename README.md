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

The router is intentionally simple and rule-based in v1. It uses registry capability metadata (capability IDs, aliases, and command examples) to derive suggested families, which reduces duplicated command-family hints across routing and planning. It improves family selection hints for planning, but does not replace validator safety checks.

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

Example:

```bash
export OTERMINUS_POLICY_MODE=write
export OTERMINUS_ALLOW_DANGEROUS=false
export OTERMINUS_ALLOWED_ROOTS=/workspace:/tmp/safe-area
export OTERMINUS_AUDIT_LOG_PATH=~/.oterminus/audit.jsonl
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
- `duration_ms`

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

In interactive REPL mode, `Tab` provides deterministic local autocomplete for built-ins (`help`, `exit`, `quit`), curated command names/categories, and local filesystem paths. Tab completion is local-only and does not call the planner or model.

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

- `ls`, `pwd`, `whoami`, `uname`, `which`, `env`
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
- “find where python is installed” → `which python`
- “count lines in README.md” → `wc -l README.md`
- “sort this file” → `sort README.md`
- “show unique lines in this file” → `uniq README.md`

When a request cannot be represented safely in these deterministic schemas, `oterminus` falls back to `experimental` mode and applies stricter confirmation behavior.

`env` is supported in curated mode, but avoid dumping full environment output when possible because it can include secrets; prefer single-variable lookups like `env PATH`.

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
