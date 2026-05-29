# Command Registry

The command registry is a merged dictionary of `CommandSpec` entries from modular command packs.

## Source packs

- `commands/filesystem.py`
- `commands/text.py`
- `commands/archive.py`
- `commands/process.py`
- `commands/system.py`
- `commands/network.py`
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
- network boundary metadata (`network_touching`)
- examples/aliases/notes

## Why registry centralization matters

Registry metadata is reused across:

- direct command detection heuristics
- router family suggestions
- planner prompt capability summaries
- validator allowlist + shape checks
- REPL `help`, `commands`, `examples`
- generated capability and command-family references

Maturity level is the registry source of truth for how a family may be presented. `structured` and
`direct_only` are normal executable states. `experimental_only` is either a constrained executable
fallback when direct support is enabled or planned/metadata-only when `direct_supported=false`.
`blocked` families are unavailable. Normal executable surfaces such as first-token autocomplete,
router suggestions, and planner prompt context must not advertise planned/metadata-only families as
available actions. Detailed help and generated references should still show their maturity/status,
direct support, risk, examples, and warnings.

`network_touching` defaults to `false`. Network diagnostics command families opt in explicitly so
prompts, discovery, validation warnings, and generated reference docs can mark the external-host
boundary without relying on command-name heuristics.

The `network` pack exposes only the `network_diagnostics` capability: fixed-count ping, HTTP HEAD
via `curl -I`, and basic `dig`/`nslookup`. The registry does not expose broad network tools or
arbitrary curl flags; validator shape checks enforce the constrained forms.

Some command families have operation-specific validation beyond the static `CommandSpec`. The
archive pack is the current example: `tar -tf` and `unzip -l` remain safe read-only operations,
while exact extraction forms and exact archive creation forms (`tar -czf ...`, `zip -r ...`) are
rendered and classified as write-risk by structured rendering and validation. The registry exposes
`zip` as a write-risk archive family because its supported surface is creation-only.

See [command families reference](../reference/command-families.md).

## Command pack availability
For the canonical behavior and env var details, see
[Command pack availability](../reference/config.md#command-pack-availability).
Profiles (`OTERMINUS_COMMAND_PROFILE`) are implemented as disabled-pack presets only; command
filtering still flows through the same registry helpers and validator checks. Registry-backed
surfaces such as prompt capability summaries, autocomplete, and REPL discovery use the effective
disabled-pack set so profile-disabled packs are not advertised as available.


## Platform-aware availability

Command packs and individual command specs can declare `supported_platforms` with normalized ids such
as `darwin`, `linux`, or `windows`. Pack-level metadata applies to every command in that pack unless
a command spec declares its own platform set. The current macOS pack is platform-specific and gates
macOS desktop commands such as `open` to `darwin`.

Registry-backed views use the effective platform when practical: prompt capability summaries, REPL
autocomplete, direct-command detection, and discovery/help output should not advertise commands that
are unavailable on the current platform. This filtering is a usability boundary only. Validator
enforcement remains authoritative, so a platform-unsupported command typed directly or returned by a
planner is rejected before execution.

## Project-health pack

The `project` pack exposes the `project_health` command family as planned/experimental metadata
(maturity `experimental_only`, `direct_supported=false`). It is intentionally excluded from normal
autocomplete, router suggestions, and planner prompt executable context until follow-up execution
support graduates the maturity metadata.

The family accepts only a strict operation enum (`run_tests`, `lint_check`, `format_check`,
`build_docs`, `run_evals`) and renders curated commands only. Arbitrary `poetry run ...` forms are
not supported by structured rendering or validation.

Because project tooling may execute local project code, the command family remains write-risk and
must keep explicit preview and confirmation when execution support is advertised.
