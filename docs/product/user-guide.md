# User Guide

## First-run Ollama setup

OTerminus requires local Ollama readiness.

Startup checks:

1. `ollama` is available on PATH.
2. Ollama service is reachable (`ollama list`).
3. At least one model is installed.

You can run diagnostics explicitly with:

```bash
poetry run oterminus doctor
```

`doctor` prints the readiness report and exits. It does not start the REPL, execute a request, or
invoke the Ollama planner.

If no model is configured yet, OTerminus shows installed models and prompts you to choose one. The
selection is saved in `~/.oterminus/config.json` (or `OTERMINUS_CONFIG_PATH` if set).

## Model selection behavior

- First run: choose from discovered local models.
- Later runs: saved model is reused.
- If saved model is missing: OTerminus warns and asks for a new selection.

## Running OTerminus

OTerminus has three user-facing CLI entry points:

- REPL mode: `poetry run oterminus`
- one-shot request mode: `poetry run oterminus "show disk usage for this folder"`
- diagnostics mode: `poetry run oterminus doctor`

### REPL mode

```bash
poetry run oterminus
```

REPL mode starts an interactive session. Requests entered in the REPL follow the same lifecycle as
one-shot requests: direct-command detection, natural-language ambiguity handling when applicable,
planning for specific natural-language requests, validation, preview, confirmation, execution, and
audit logging.

REPL built-ins include (all local, deterministic, and backed by command-registry metadata; they do not call Ollama):

- `help`, `help capabilities`, `help <capability_id>`, `help <command_family>`
- `capabilities`, `commands`, `examples`
- `history`, `history <n>`, `explain <history_id>`, `rerun <history_id>`
- `dry-run <request>`, `explain <request>`
- `audit status`, `audit tail [n]`, `audit clear`, `exit`, `quit`

### One-shot mode

```bash
poetry run oterminus "find all .py files"
```

One-shot mode accepts the remaining command-line words as a single request. It detects direct
commands first, checks non-direct natural-language requests for ambiguity, plans specific
natural-language requests, validates accepted proposals, renders a preview, and asks for
confirmation before execution.

### Doctor mode

```bash
poetry run oterminus doctor
```

Doctor mode is diagnostic-only. It prints readiness and integrity checks, including configuration,
selected model, Ollama CLI/service/model availability, audit path, registry, eval fixture, and
developer-tool status where applicable. It exits with the doctor report status and does not start
the REPL, execute a request, or invoke the Ollama planner.

### Direct commands

You can enter supported command families directly (for example `ls -la`, `cd src`, `pwd`, or
`ping -c 4 example.com`).

Direct commands skip LLM planning when local direct-command detection succeeds. They still pass
through validator + policy gates and show a preview before any execution. In normal execute mode,
they still require confirmation.

Network direct commands are detected only for exact constrained forms: `ping -c <count> <host>`,
`curl -I <http-or-https-url>`, `dig <domain>`, and `nslookup <domain>`. Broad network commands
cannot bypass validation through the direct-command path.

### Natural-language requests

You can ask for tasks like:

- “show disk usage for this folder”
- “search TODO in Python files”
- “find processes matching python”
- “show HTTP headers for https://example.com”
- “look up DNS for example.com”

These requests first pass through ambiguity detection. If the request is specific enough, it goes
through capability routing and planning before validation.

### Ambiguous natural-language requests

OTerminus may stop vague natural-language requests before any planner call. Examples include:

```text
clean this folder
delete unnecessary files
repair permissions
make this project work
```

Expected behavior:

- OTerminus stops before planning.
- It shows that the request is ambiguous and includes the reason when useful.
- It suggests safe read-only inspection alternatives, such as listing large files, recently modified
  files, temporary-looking files, project files, or inspecting permissions.
- It does not ask for confirmation and does not execute anything.

Use a more specific request when you know the target and action. Specific requests can continue to
routing, planning, validation, preview, and confirmation, for example:

```text
list large files in this folder
show permissions for run.sh
make run.sh executable
```

Ambiguity detection is only for vague natural-language requests. Direct shell commands such as
`chmod +x run.sh` or `rm -rf build` are not intercepted as ambiguous; they continue to the direct
command path and must still pass validator and policy checks before any execution.

## Proposal modes in previews

Previews show the proposal mode so you can understand how OTerminus will handle the command:

- **Structured** is the normal, preferred path. OTerminus uses a curated `command_family` and typed
  `arguments`, then renders the final command deterministically.
- **Experimental** is a constrained fallback for command text that cannot be represented by
  structured arguments yet. It is still strictly validated and requires stronger confirmation.

If validation or policy checks fail, OTerminus does not ask for execution confirmation.

## Safety/inspection modes

### Dry run

```bash
poetry run oterminus --dry-run "copy notes.txt to backup/notes.txt"
```

Dry run is a safety preview for checking what OTerminus would do. It still follows the normal
inspection path: detect a direct command when possible, or plan a specific natural-language request
after ambiguity checks; then validate the proposal and render the preview. It stops there: dry run
does not show a confirmation prompt and never executes the command.

Use dry run when you want to verify detection, planning, validation, policy outcome, and the final
rendered command before deciding whether to run the request normally. Direct commands that can be
detected locally skip Ollama planning, so a command like `poetry run oterminus --dry-run "ls"` does
not require a live Ollama service. Ambiguous natural-language requests stop before planning.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`dry-run <request>` instead.

### Explain mode

```bash
poetry run oterminus --explain "show running processes"
```

Explain mode is for learning and debugging why OTerminus chose a command. Like dry run, it performs
direct-command detection or natural-language planning, validation, and preview, then skips the
confirmation prompt and execution. It additionally renders reasoning about the selected command,
available flag or argument meanings, risk level, and policy interpretation, including blocked-policy
rationale when validation or policy rejects a proposal.

Use explain mode when you want to understand the path from request to command rather than simply
check the final preview. Direct commands that can be detected locally skip Ollama planning, so a
command like `poetry run oterminus --explain "ls"` does not require a live Ollama service. Ambiguous
natural-language requests stop before planning.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`explain <request>` or `explain <history_id>` instead.

## REPL session history and rerun safety

REPL always keeps in-memory session history for the current process. Persistent history is optional
and controlled by `OTERMINUS_HISTORY_ENABLED` (default `false`).

- When `OTERMINUS_HISTORY_ENABLED=false`, history is session-local only and is cleared when you exit
  the REPL.
- When `OTERMINUS_HISTORY_ENABLED=true`, OTerminus also appends local JSONL records to
  `OTERMINUS_HISTORY_PATH` (default `~/.oterminus/history.jsonl`).
- `OTERMINUS_HISTORY_LIMIT` controls how many recent persisted records are loaded into the next REPL
  session (default `100`; the env value must be a valid integer; loaded values are clamped to at least `1`).
- `OTERMINUS_HISTORY_REDACT` controls redaction before persisted writes and defaults to the current
  audit-redaction setting (`OTERMINUS_AUDIT_REDACT`) when unset.

History commands:

- `history` shows all loaded records for the current REPL session (session records plus any loaded
  persisted records, when enabled).
- `history <n>` shows the most recent `n` records.
- `explain <history_id>` explains the recorded plan/validation result for that entry and **never
  executes**.
- `rerun <history_id>` replays the original user input through the full request lifecycle again
  (ambiguity checks when applicable, planning/direct-detection path, validation/policy, preview, and
  explicit confirmation before execution).

`rerun` does not execute previously rendered command text directly, and cannot bypass policy gates
for rejected, ambiguous, cancelled, dry-run, or explain-only outcomes.

History output and persisted history files may include command text, local paths, and execution
context. Review carefully before sharing terminal screenshots or history snippets publicly.

`--dry-run` and `--explain` are mutually exclusive and apply to requests, not to the `doctor`
diagnostics command. For example, `poetry run oterminus --dry-run doctor` and
`poetry run oterminus doctor --dry-run` are invalid combinations.

## Autocomplete

Tab completion is available only in interactive REPL mode (`poetry run oterminus`) and is local
(`prompt_toolkit`) for:

- built-ins
- supported command families
- capability IDs (and optional capability hints)
- local filesystem paths

Autocomplete is deterministic and does not call Ollama.

If tab completion does not work:

```bash
poetry install
poetry run oterminus
```

If you use a globally installed or `pipx` build, rebuild/reinstall after dependency changes.

## Clear command

`clear` is supported and handled specially by the local executor using ANSI clear-screen output.

## Audit management commands

Audit logs are local JSONL files (default: `~/.oterminus/audit.jsonl`) and are not uploaded by
OTerminus.

- `audit status` shows whether audit is enabled, the active path, file presence, and redaction
  state.
- `audit tail` shows the most recent 10 events; `audit tail <n>` shows the newest `n` events.
- `audit clear` prompts for exact confirmation (`CLEAR AUDIT`) before clearing the local audit log.

When audit logging is disabled (`OTERMINUS_AUDIT_ENABLED=false`), tail/clear commands report that
audit is disabled and do not create a log file.

Redaction is enabled by default (`OTERMINUS_AUDIT_REDACT=true`). Even with redaction, logs may
still contain local paths and command context, so review before sharing publicly.

## Safety expectations

- OTerminus may block ambiguous broad/destructive natural-language requests before planning and
  suggest safer read-only inspections.
- Direct shell commands are not intercepted as ambiguous; they still go through validation and
  policy checks.
- Unsupported flags, operators, redirection/pipeline chains, and disallowed paths are rejected.
- Experimental mode is a constrained fallback and requires stronger confirmation.
- Commands that fail validation or policy checks are never executed.

## Network diagnostics

OTerminus is local-first by default. The `network_diagnostics` capability is intentionally small and
read-only, but it still contacts external hosts and may reveal your IP address, DNS query, target
host, or other network metadata. Preview/help text shows the network warning, and execution still
requires confirmation.

Supported operations:

- `ping -c <count> <host>` with count from 1 to 10
- `curl -I <http-or-https-url>` for HTTP HEAD only
- `dig <domain>`
- `nslookup <domain>`

Unsupported operations include POST/PUT/PATCH/DELETE, request bodies, arbitrary headers,
authorization headers, cookies, downloads, scanning, traceroute, SSH/SCP, netcat, nmap, wget,
network commands through sudo, arbitrary network shell commands, and shell pipelines/redirection.
OTerminus is still not a general network automation tool.

## Command pack availability
You can disable specific command packs with `OTERMINUS_DISABLED_COMMAND_PACKS`. For the exact
format, validation rules, and behavior details, see
[Command pack availability](../reference/config.md#command-pack-availability).

You can also choose a profile preset with `OTERMINUS_COMMAND_PROFILE`:
`beginner`, `safe`, `developer`, or `power`. Profiles are convenience presets for disabled packs
only; policy mode, validation, and confirmation remain authoritative.


## Platform-specific commands
Some command families are platform-specific. For example, `open` is available by default on macOS (`darwin`) only. On unsupported platforms, these commands are hidden from suggestions and planner hints, and rejected by validator before execution.

## Output size guards

Execution output can be large for commands like `cat`, `grep`, `find`, `ps`, and `lsof`. OTerminus truncates each captured stream (stdout and stderr) to `OTERMINUS_MAX_OUTPUT_CHARS` (default `20000`) after command completion, and prints a clear truncation notice when this happens.

Dry-run/explain paths are unchanged because they do not execute commands. Audit logs and persisted history do not store full stdout/stderr content.

## Git inspection (read-only)

OTerminus supports **read-only Git inspection** in curated mode. You can ask directly (for example `git status --short`) or in natural language (for example "show git status" or "show last 5 commits").

Supported operations:
- `git status --short`
- `git branch --show-current`
- `git log --oneline -n <count>`
- `git diff --stat`
- `git diff --name-only`

Explicitly unsupported in curated mode:
- Git mutation operations (`git add`, `git commit`, `git checkout`, `git switch`, `git restore`, `git reset`, `git clean`, `git merge`, `git rebase`, `git stash`)
- Git network operations (`git push`, `git pull`, `git fetch`)
- Arbitrary Git subcommands not represented by the structured Git inspection schema

All requests still go through routing, planning, validation, and confirmation policy checks. OTerminus is not a replacement for Git automation workflows.

## Archive inspection, extraction, and creation

Archive support includes read-only inspection, guarded extraction, and guarded creation for local
tar and zip files. Inspection is safe-risk. Extraction and creation are write-risk because they can
create files and may overwrite existing files depending on the underlying archive tool behavior.

Supported inspection operations:
- `tar -tf <archive>`
- `unzip -l <archive>`

Supported extraction operations:
- `tar -xf <archive> -C <destination>`
- `unzip <archive> -d <destination>`

Supported creation operations:
- `tar -czf <archive_path> <source_paths...>`
- `zip -r <archive_path> <source_paths...>`

Extraction rules:
- destination is required and must be explicit
- extraction to `/` and broad system roots is rejected
- configured `allowed_roots` policy is applied to archive and destination paths
- preview and confirmation are required before execution
- users should inspect archives before extracting them

Creation rules:
- output archive path and every source path must be explicit
- source path `/`, broad system roots, broad home-directory targets, `.`, `..`, and wildcards are
  rejected
- configured `allowed_roots` policy is applied to output archive paths and source paths
- archive creation may overwrite or update an existing archive path depending on the underlying
  `tar` or `zip` behavior
- preview and confirmation are required before execution

Explicitly unsupported in this stage:
- extraction without an explicit destination (`tar -xf archive.tar`, `unzip archive.zip`)
- overwrite flags such as `unzip -o`
- password-protected archives, encryption, split archives, append/update flags, deleting sources
  after compression, arbitrary tar/zip/unzip options, path-transforming tar options, wildcard
  source or archive selection, hidden automatic source discovery, recursive archive operations,
  network archive URLs, and `sudo`

Archive commands still go through validation and confirmation before execution. Unsupported archive
forms are rejected rather than treated as broad shell access.

OTerminus does not claim full protection from malicious archive contents in this PR. It validates
the command shape, archive path, destination path, and policy boundaries, but it does not inspect
archive member paths or block path traversal inside archive contents before calling `tar` or
`unzip`.

## Failure explanations (opt-in)

If `OTERMINUS_EXPLAIN_FAILURES=true`, OTerminus may print a concise explanation after a confirmed command exits non-zero.

- Runs only after command execution (not in dry-run/explain modes).
- Never auto-executes suggested next actions.
- Suggestions are guidance only (`dry-run`/`copy-only`).
- Context sent to explanation is redacted and truncated.

For exact environment variables, see [Configuration reference](../reference/config.md#failure-explanations-opt-in).


## Project health capability

The `project_health` capability provides curated executable checks (`run_tests`, `lint_check`,
`format_check`, `build_docs`, `run_evals`) through deterministic structured rendering.

Supported natural-language requests include: run tests, check linting, check formatting, build
docs, and run evals.

Unsupported requests include dependency/package management (`poetry add`, `poetry install`,
`poetry update`, `pip install`, `npm install`, `brew install`), write-formatting (`ruff format .`),
deploy/publish operations, and arbitrary `poetry run ...` commands.

These operations may execute local project code and tooling, so preview and explicit confirmation
are always required. This capability is not arbitrary shell support.
