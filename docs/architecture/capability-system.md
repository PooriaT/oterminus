# Capability System

OTerminus groups commands into workflow capabilities rather than exposing unrestricted shell
behavior.

## Why capability-first

- keeps planner context compact and stable
- enables policy and UX at workflow level
- avoids unbounded command/flag surfaces
- improves explainability for contributors and users

## Capability metadata

Each command spec includes:

- `capability_id`
- `capability_label`
- `capability_description`
- `network_touching` for commands that contact external hosts
- command examples and natural-language aliases

Capability summaries are derived from merged registry metadata and reused for prompts and REPL
discovery (`capabilities`, `commands`, `examples`, and `help <target>`). These discovery commands are local and deterministic; they do not invoke planner, validator, policy, executor, or Ollama.

## Network boundary

OTerminus is local-first by default. A command that contacts external hosts crosses that boundary
even when the command is read-only, because it can reveal the user's IP address, DNS query, target
host, or other network metadata.

Network-touching command families must set `network_touching=True` in their `CommandSpec`.
Capability summaries, planner context, generated reference docs, validation warnings, and REPL help
can then surface that boundary consistently. This metadata does not grant permission to execute a
network command; validation and policy remain authoritative, and user confirmation is still required
before execution.

The initial `network_diagnostics` capability is limited to `ping -c <count> <host>`,
`curl -I <url>`, `dig <domain>`, and `nslookup <domain>`. It does not make OTerminus a general
network automation tool: mutating HTTP methods, secret headers, cookies, downloads, scanning, SSH,
SCP, nmap, wget, netcat, sudo network commands, arbitrary flags, and shell pipelines/redirection
remain unsupported.

## Current capability domains

- `filesystem_inspection`
- `filesystem_mutation`
- `text_inspection`
- `process_inspection`
- `system_inspection`
- `network_diagnostics`
- `macos_desktop`
- `destructive_operations`

See [reference capability map](../reference/capability-map.md).

## Command pack availability
Command-pack enable/disable behavior is documented in the configuration reference:
[Command pack availability](../reference/config.md#command-pack-availability).
Profile presets (`beginner`, `safe`, `developer`, `power`) only change pack availability; they do
not replace policy mode and they do not bypass validation or confirmation. Disabled capabilities are
hidden from planner context, route suggestions, autocomplete, and REPL discovery; validator still
rejects disabled command families before execution.


## Platform-aware capability visibility
Capability summaries are built from platform-filtered command families, so platform-specific capabilities (for example `macos_desktop`) are only advertised where supported.

## Git capability scope

The `git_inspection` capability is intentionally scoped to read-only inspection. Registry metadata defines examples, aliases, and warnings so discovery surfaces (`capabilities`, `commands`, `examples`, `help <capability>`) remain consistent without duplicate hardcoded lists.

`git_inspection` does not permit arbitrary `git ...` execution in structured mode; only the approved operation enum is allowed.

## Capability: `project_health`

`project_health` is a curated developer-workflow capability for common repository health checks:
`run_tests`, `lint_check`, `format_check`, `build_docs`, and `run_evals`.

It is executable via deterministic structured rendering with a strict, closed operation set:
- `run_tests` -> `poetry run pytest`
- `lint_check` -> `poetry run ruff check .`
- `format_check` -> `poetry run ruff format --check .`
- `build_docs` -> `poetry run mkdocs build --strict`
- `run_evals` -> `poetry run oterminus-evals`

Safety boundary:
- always preview and require explicit confirmation
- reject arbitrary `poetry run ...` commands
- reject dependency install/update commands
- reject write-format (`poetry run ruff format .`)
- reject shell chaining/pipes/redirection/substitution
