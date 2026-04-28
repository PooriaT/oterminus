# Adding Command Families Safely

Part of the docs handbook: see [docs index](index.md).

This guide explains how to add new command families and capability packs to OTerminus **without weakening safety guarantees**.

OTerminus is intentionally **curated**. It should not become a giant shell encyclopedia that tries to support every Unix command and every possible flag combination. The preferred path is to support high-value workflows with deterministic structured rendering.

## Core concepts

### What is a command family?
A command family is a curated base command entry in the registry (`CommandSpec`), such as `ls`, `grep`, `cp`, or `rm`.

Each family defines:
- safety and policy metadata (`risk_level`, `maturity_level`)
- validation shape (operands and allowed flags)
- capability mapping (`capability_id`, label, description)
- direct-command detection behavior

### What is a capability pack?
A capability pack is a module-level tuple of command specs (for example `filesystem`, `text`, `process`, `system`, `macos`, `dangerous`) that is merged into the global command registry.

Capability packs group commands by workflow intent (for example filesystem inspection vs mutation), not by “all flags from man pages.”

## Design principles (read before adding anything)

1. **Curate, don’t mirror shells.** Only add commands that support clear user workflows.
2. **Structured-first is the default.** Prefer deterministic command-family renderers over raw command execution.
3. **Experimental mode is a constrained fallback.** It is not a shortcut for skipping structured design.
4. **Small allowlists beat broad compatibility.** Keep flags/operands intentionally minimal.
5. **Safety metadata is mandatory.** Every command must have explicit risk and maturity policy.

## Step-by-step: add a new command family

## 1) Choose capability placement and define metadata
- Put the new command in the correct capability pack under `src/oterminus/commands/`.
- Reuse an existing capability when it matches the workflow; introduce a new capability only when needed.
- Ensure `capability_id` is non-empty and stable.

Recommended: start by copying the style of nearby command specs in the same pack.

## 2) Choose maturity level correctly
Set `maturity_level` intentionally:

- `structured`: command participates in deterministic structured mode.
- `direct_only`: command can be accepted only as direct user command, but no structured renderer exists yet.
- `experimental_only`: command is allowed only through constrained experimental path (higher friction).
- `blocked`: explicitly tracked but blocked from execution.

Use these rules:
- Pick **`structured`** when command behavior can be represented with a stable schema and renderer.
- Pick **`direct_only`** when direct invocation is needed now, but structured schema is not yet safe/clear.
- Pick **`experimental_only`** only when there is a justified temporary gap and strong constraints remain.
- Pick **`blocked`** for privileged/high-impact commands that should never execute in curated policy.

If uncertain, start stricter (`experimental_only` or `blocked`) and relax later with tests.

## 3) Assign `risk_level` with justification
Use least privilege:

- `safe`: read-only inspection or metadata queries.
- `write`: local mutations that do not require elevation and have bounded blast radius.
- `dangerous`: destructive, privileged, or broad-impact operations.

Document your reasoning in code review/PR notes. Risk should align with:
- data-loss potential
- privilege implications
- breadth of target scope
- reversibility

## 4) Define minimal allowed flags
In `CommandSpec`, explicitly model supported flags:
- `allowed_flags`
- `flags_with_values`
- `path_valued_flags`
- `leading_flags*` for commands like `find`

Guidelines:
- Start with the smallest useful subset.
- Do **not** bulk-copy man-page flags.
- Add flags only when backed by workflow need + tests.
- Reject unsupported flags by default.

## 5) Handle dangerous flags explicitly
If specific flags increase blast radius (example recursive deletion), mark them in `dangerous_flags`.

Expected behavior:
- validator may escalate risk/warnings when these flags appear
- policy gating should still apply

Also model dangerous literals when needed (`dangerous_target_literals`) and forbidden operand prefixes (`forbidden_operand_prefixes`) for unsafe targets like URLs or broad system paths.

## 6) Define path operand behavior explicitly
If command accepts paths, set or validate path behavior deliberately:

- Set `path_operand_mode` when non-default parsing is needed (`CD`, `FIND`).
- Ensure value-taking flags that point to paths are listed in `path_valued_flags`.
- Confirm allowed-roots policy checks cover both operands and path-valued flags.

Never assume path handling is implicit. Make it explicit in spec + tests.

## 7) Add/extend structured support when maturity is `structured`
When a command is part of structured mode:
- add argument schema validation in `structured_commands.py`
- add deterministic rendering logic
- ensure ambiguous or unsafe forms are rejected

A command marked `structured` should have an end-to-end deterministic path.

## 8) Add validator and direct-command tests
At minimum, add tests for:

- registry metadata (`capability_id`, flags, risk/maturity)
- validator acceptance for valid forms
- validator rejection for invalid flags/shape
- dangerous-flag behavior and risk escalation (if applicable)
- allowed-roots path checks (if paths involved)
- direct-command detection behavior (`direct_supported`, heuristics)

Prefer focused tests in:
- `tests/test_command_registry.py`
- `tests/test_validator.py`
- `tests/test_direct_commands.py`
- `tests/test_structured_commands.py` (for structured renderers)

## 9) Add eval fixtures
Update regression eval fixtures under `evals/cases/`.

Include representative cases for:
- expected mode (`structured` vs `experimental`)
- command family routing
- expected risk level
- acceptance/rejection behavior
- rendered command + argv when deterministic

Add both “happy path” and “should fail” fixtures for new family behavior.

## 10) Update autocomplete and docs
If your change introduces a new command/capability visible to users:

- verify completion behavior still works for first-token suggestions and capability hints
- add/adjust completion tests if needed
- update README and contributor docs when behavior/policy changes

Documentation should explain workflow intent, not just command syntax.

## Acceptance checklist

Before merging, confirm all of the following:

- [ ] Command has a `capability_id`.
- [ ] Risk level is explicitly justified.
- [ ] Allowed flags are minimal and intentional.
- [ ] Dangerous flags are marked when applicable.
- [ ] Path handling is explicit if paths are accepted.
- [ ] Structured renderer exists if command is part of structured mode.
- [ ] Validator tests exist.
- [ ] Direct-command tests exist where applicable.
- [ ] Eval fixtures exist.
- [ ] README/docs are updated.
- [ ] Command does not require `sudo` or broad system mutation unless explicitly blocked or dangerous.

## Practical scope reminder

A good command-family addition makes OTerminus **more deterministic, auditable, and safe**.

If a proposed command would require huge flag coverage, fragile parsing, or privileged mutations, prefer one of:
- a smaller curated subset,
- an explicit experimental-only constraint,
- or an explicit blocked entry with rationale.
