# User Guide

## Public install / normal user flow

For released versions, OTerminus is published to PyPI as the `oterminus` package. The package
installs two console scripts: `oterminus` for the assistant CLI and `oterminus-evals` for the
packaged evaluation smoke check.

For normal CLI use, prefer `pipx` because it installs OTerminus in an isolated environment instead
of mixing OTerminus and its dependencies into your system Python environment:

```bash
pipx install oterminus
oterminus --version
oterminus doctor
oterminus
```

Run `oterminus --version` after installation to confirm the installed package version. Then run
`oterminus doctor`; it is the recommended post-install diagnostic for checking the detected
package version, Python runtime, executable path, pipx or virtualenv context, platform,
configuration paths, selected model state, Ollama CLI/service readiness, local model availability,
audit/history paths, registry metadata, eval fixtures, and relevant developer-tool status.

## Supported environments

OTerminus currently targets macOS and Unix-like POSIX terminal environments. Linux-like
environments may work when Python 3.13+, Ollama, and the required shell commands are installed.
Native Windows Command Prompt and PowerShell are not first-class supported targets yet; Windows
users should run OTerminus inside WSL when they need the Unix-like shell behavior expected by the
current command registry.

Command packs and individual command specs can be platform-aware. The macOS desktop pack, including
`open`, is available only on supported macOS (`darwin`) platforms. Unsupported platform commands are
hidden from autocomplete, planner context, and discovery output where practical, but the validator
remains the authoritative boundary and rejects platform-unsupported commands before execution.

After `doctor` reports a usable setup, start the interactive app or run one-shot requests:

```bash
oterminus
oterminus "show disk usage for this folder"
oterminus --dry-run "copy notes.txt to backup/notes.txt"
oterminus --explain "find processes matching python"
```

## Upgrade and uninstall

Update an existing isolated `pipx` install with:

```bash
pipx upgrade oterminus
oterminus --version
```

The version check is a lightweight package diagnostic and does not require Ollama.

Remove the isolated CLI with:

```bash
pipx uninstall oterminus
```

## pip fallback

If `pipx` is not available, you can install from PyPI with pip:

```bash
python -m pip install oterminus
```

`pipx` remains preferred for command-line use because it keeps the OTerminus application environment
separate from your system Python and from other Python projects.

## Development install

Use Poetry only when you are developing OTerminus from a source checkout:

```bash
poetry install
poetry run oterminus
```

Development commands can use the same CLI forms with a `poetry run` prefix, for example
`poetry run oterminus --version`, `poetry run oterminus doctor`, or
`poetry run oterminus --dry-run "ls"`. Local wheel/package validation with
`poetry run python scripts/validate_package_install.py` is a contributor and release-maintainer
workflow, not the primary user install path. See the
[contributor workflow](../contributing.md#local-package-build-wheel-install-validation) and
[release guide](../release.md) for package validation and publishing details.

## Ollama requirement for natural-language planning

PyPI installation gives you the OTerminus CLI; it does not install Ollama, start the Ollama service,
or download a local model. Ollama is still required for natural-language planning. Direct commands
and some deterministic local paths may skip model planning, but first-run natural-language usage
depends on Ollama being ready.

Startup and doctor readiness checks include:

1. `ollama` is available on PATH.
2. Ollama service is reachable (`ollama list`).
3. At least one model is installed.

Check only the installed package version with:

```bash
oterminus --version
oterminus version
```

Both version forms print the same concise package version, exit successfully, and do not start the
REPL, run doctor/setup checks, read or write request history, or require Ollama. Inside the REPL,
`version` prints the same diagnostic output without going through natural-language planning.

Run environment diagnostics explicitly with:

```bash
oterminus doctor
```

`doctor` prints the readiness report and exits. It does not start the REPL, execute a request, or
invoke the Ollama planner. Unlike `--version`, it checks environment readiness such as Ollama
availability. If Ollama is missing, not running, or has no installed model, `doctor` should report
that clearly so you can fix the local model setup before natural-language planning.

If no model is configured yet, OTerminus shows installed models and prompts you to choose one. The
selection is saved in `~/.oterminus/config.json` (or `OTERMINUS_CONFIG_PATH` if set).

## Doctor troubleshooting

Run `oterminus doctor` after a PyPI or `pipx` install and after changing Ollama, config, audit, or
history settings. Doctor is diagnostics-only: it reports readiness and suggested next steps, but it
does not install Ollama, start services, download models, edit config, or write audit/history
records.

The report groups checks by package/runtime, platform, Ollama, model/config, local files, optional
features, and developer-only checks:

- `package import` and `oterminus version` mean the installed OTerminus package can be imported and
  package metadata is visible. A source checkout may warn that package metadata is unavailable and a
  local fallback version is being used.
- `python runtime` shows the Python version and executable path. Unsupported Python is a critical
  failure; install Python 3.13 or newer, then reinstall OTerminus in that environment.
- `environment` and `install context` identify virtualenv and likely `pipx` installs when practical.
  Detection is best-effort; unknown context is a hint, not proof of a broken install.
- `ollama CLI` missing means the `ollama` executable is not on PATH. Install Ollama, then rerun
  doctor.
- `ollama service` failing means the CLI exists but `ollama list` cannot reach the local service.
  Start Ollama, for example with `ollama serve`, then rerun doctor.
- `local ollama models` failing means the service is reachable but no local models are installed.
  Pull a model, for example `ollama pull gemma4`.
- `configured model` warns when no model has been selected yet. Run OTerminus once to choose from
  installed models, or set the `model` field in the config JSON. If the configured model is missing,
  pull that model or update the config to an installed model.
- `config path`, `audit log path`, and `history path` show whether OTerminus can read or create the
  relevant local directories. Audit logging is enabled by default; persistent history is disabled by
  default, so a disabled history check is normally OK.
- `eval fixtures` and `dev tools` are developer-only checks. They may warn when doctor is run from a
  source checkout, but they are not expected for normal PyPI or `pipx` installs.

Direct commands may still work without a configured model because they can skip LLM planning after
local detection. Natural-language planning needs Ollama installed, running, at least one local model
available, and a selected configured model.

## Shell completion strategy

OTerminus separates two different completion surfaces:

1. **Shell-level completion** happens in your outer shell before OTerminus starts. OTerminus does
   not currently ship generated completion scripts for zsh, bash, or fish. Installing or upgrading
   OTerminus with `pipx` does not edit `.zshrc`, `.bashrc`, `config.fish`, or any other shell
   startup file automatically.
2. **REPL Tab autocomplete** happens inside interactive OTerminus after you run `oterminus`. This
   is supported through `prompt_toolkit` and is documented in the [Autocomplete](#autocomplete)
   section. It completes built-ins, supported commands/capabilities, and local filesystem paths.

Current shell-level status:

| Shell | OTerminus shell-level completion status |
| --- | --- |
| zsh | No generated `_oterminus` completion script is shipped. |
| bash | No generated `oterminus` completion script is shipped. |
| fish | No generated `oterminus.fish` completion script is shipped. |

If shell-level completion is added later, it should remain opt-in and documented as manual shell
configuration chosen by the user, not as an automatic install-time or runtime mutation.

## Model selection behavior

- First run: choose from discovered local models.
- Later runs: saved model is reused.
- If saved model is missing: OTerminus warns and asks for a new selection.

## Running OTerminus

OTerminus has three user-facing CLI entry points:

- REPL mode: `oterminus`
- one-shot request mode: `oterminus "show disk usage for this folder"`
- diagnostics mode: `oterminus doctor`

Use the same commands with a `poetry run` prefix when running from a source checkout.

### REPL mode

```bash
oterminus
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
oterminus "find all .py files"
```

One-shot mode accepts the remaining command-line words as a single request. It detects direct
commands first, checks non-direct natural-language requests for ambiguity, plans specific
natural-language requests, validates accepted proposals, renders a preview, and asks for
confirmation before execution.

### Doctor mode

```bash
oterminus doctor
```

Doctor mode is diagnostic-only. It prints readiness and integrity checks, including configuration,
selected model, Python runtime, install context, Ollama CLI/service/model availability,
audit/history paths, registry, eval fixture, and developer-tool status where applicable. It exits
with the doctor report status and does not start the REPL, execute a request, or invoke the Ollama
planner.

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
oterminus --dry-run "copy notes.txt to backup/notes.txt"
```

Dry run is a safety preview for checking what OTerminus would do. It still follows the normal
inspection path: detect a direct command when possible, or plan a specific natural-language request
after ambiguity checks; then validate the proposal and render the preview. It stops there: dry run
does not show a confirmation prompt and never executes the command.

Use dry run when you want to verify detection, planning, validation, policy outcome, and the final
rendered command before deciding whether to run the request normally. Direct commands that can be
detected locally skip Ollama planning, so a command like `oterminus --dry-run "ls"` does
not require a live Ollama service. Ambiguous natural-language requests stop before planning.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`dry-run <request>` instead.

### Explain mode

```bash
oterminus --explain "show running processes"
```

Explain mode is for learning and debugging why OTerminus chose a command. Like dry run, it performs
direct-command detection or natural-language planning, validation, and preview, then skips the
confirmation prompt and execution. It additionally renders reasoning about the selected command,
available flag or argument meanings, risk level, and policy interpretation, including blocked-policy
rationale when validation or policy rejects a proposal.

Use explain mode when you want to understand the path from request to command rather than simply
check the final preview. Direct commands that can be detected locally skip Ollama planning, so a
command like `oterminus --explain "ls"` does not require a live Ollama service. Ambiguous
natural-language requests stop before planning.

The CLI flag is for one-shot requests only. Inside the REPL, use the built-in form
`explain <request>` or `explain <history_id>` instead.

When you run with `--verbose`, trace output includes fast-path diagnostics (`fast_path=direct_command`
or `fast_path=ambiguity_blocked`), planner invocation status (`planner=invoked`), and a concise timing summary (for example: `[trace] timings direct=1ms route=1ms planner=skipped ... total=4ms`).

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
context. Persisted history does not store stdout/stderr, full failure output, or raw planner
responses, and `OTERMINUS_HISTORY_REDACT` is enabled by default when audit redaction is enabled.
Review carefully before sharing terminal screenshots or history snippets publicly.

`--dry-run` and `--explain` are mutually exclusive and apply to requests, not to the `doctor` or
`version` diagnostics commands. For example, `poetry run oterminus --dry-run doctor`,
`poetry run oterminus doctor --dry-run`, and `poetry run oterminus --dry-run version` are invalid
combinations.

## Autocomplete

REPL Tab autocomplete is available only inside interactive REPL mode (`oterminus`, or
`poetry run oterminus` from a development checkout) and is local (`prompt_toolkit`) for:

- built-ins
- supported command families
- capability IDs (and optional capability hints)
- local filesystem paths

Autocomplete is deterministic and does not call Ollama. It is separate from shell-level completion:
zsh, bash, and fish are not modified automatically and OTerminus does not currently install shell
completion scripts for the outer command.

If REPL Tab autocomplete does not work:

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

Redaction is enabled by default (`OTERMINUS_AUDIT_REDACT=true`). Audit events store output
truncation metadata and exit codes, not full stdout/stderr. Even with redaction, logs may still
contain local paths, command context, and validation decisions, so review before sharing publicly.

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

## Environment variable lookup privacy

Curated `env` support is intentionally narrow because full environment output often includes
secrets. Bare `env` and multi-variable dumps are rejected; accepted requests use a single variable,
for example `env PATH`. OTerminus still warns that environment values may contain secrets, and
secret-like lookups such as `env TOKEN` should not be pasted into public issues, chats, logs, or
screenshots without review.

## Command pack availability
You can disable specific command packs with `OTERMINUS_DISABLED_COMMAND_PACKS`. For the exact
format, validation rules, and behavior details, see
[Command pack availability](../reference/config.md#command-pack-availability).

You can also choose a profile preset with `OTERMINUS_COMMAND_PROFILE`:
`beginner`, `safe`, `developer`, or `power`. Profiles are convenience presets for disabled packs
only; policy mode, validation, and confirmation remain authoritative. Disabled packs are hidden from
autocomplete, planner hints, and discovery output, and disabled commands are rejected before
execution even when typed directly.


## Platform-specific commands
Some command families are platform-specific. For example, `open` is available by default on macOS
(`darwin`) only. On unsupported platforms, these commands are hidden from suggestions and planner
hints where practical, and rejected by the validator before execution.

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
- Context sent to explanation is redacted and truncated before it is sent to the configured local Ollama model. Full audit logs and persisted history are not sent.
- Model-returned suggested actions and summaries are redacted before display/audit metadata where applicable.

For exact environment variables, see [Configuration reference](../reference/config.md#failure-explanations-opt-in).


## Project health capability

The `project_health` capability is a supported curated developer workflow. It uses structured
operations only and renders exact project-tooling commands:

- `run_tests` -> `poetry run pytest`
- `lint_check` -> `poetry run ruff check .`
- `format_check` -> `poetry run ruff format --check .`
- `build_docs` -> `poetry run mkdocs build --strict`
- `run_evals` -> `poetry run oterminus-evals`

Clear requests such as `run tests`, `check linting`, `run format check`, `build docs`, and
`run evals` can be planned deterministically without Ollama. They still only produce a proposal:
validation, preview, policy checks, and explicit confirmation happen before any execution.

Unsupported requests include dependency/package management (`poetry add`, `poetry install`,
`poetry update`, `pip install`, `npm install`, `brew install`), write-formatting (`ruff format .`),
deploy/publish operations, and arbitrary `poetry run ...` commands.

These operations may execute local project code and tooling. This capability is not arbitrary shell
support or arbitrary Poetry command support.

OTerminus also has a conservative deterministic local planner for a small set of clear natural-language requests (for example: `show current directory`, `show files`, `show disk usage`). This fast path only builds structured proposals; it never executes directly and still requires validation, preview, and confirmation.
