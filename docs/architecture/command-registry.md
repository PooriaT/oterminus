# Command Registry

The command registry is a merged dictionary of `CommandSpec` entries from modular command packs.

## Source packs

- `commands/filesystem.py`
- `commands/text.py`
- `commands/archive.py`
- `commands/process.py`
- `commands/system.py`
- `commands/macos.py`
- `commands/dangerous.py`

Registry merge rejects duplicate command names and empty capability IDs.

## What `CommandSpec` defines

- command name/category
- capability mapping
- risk level and maturity level
- direct detection behavior
- flag model (`allowed_flags`, `flags_with_values`, path-valued/leading flags)
- operand constraints (`min_operands`, `max_operands`)
- path safety metadata (`forbidden_operand_prefixes`, path operand mode)
- examples/aliases/notes

## Why registry centralization matters

Registry metadata is reused across:

- direct command detection heuristics
- router family suggestions
- planner prompt capability summaries
- validator allowlist + shape checks
- REPL `help`, `commands`, `examples`

See [command families reference](../reference/command-families.md).

## Command pack availability
For the canonical behavior and env var details, see
[Command pack availability](../reference/config.md#command-pack-availability).


## Platform-aware availability
Command specs can declare `supported_platforms` (normalized ids: `darwin`, `linux`, `windows`). Unsupported commands are filtered from prompt/autocomplete registry views, but validation remains authoritative and rejects unsupported commands before execution.
