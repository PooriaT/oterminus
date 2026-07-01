# Policy Modes

Policy controls are configured through environment variables and applied during validation.

## Risk levels

Each command family carries a risk level:

- `safe`
- `write`
- `dangerous`

## Mode semantics

`OTERMINUS_POLICY_MODE`:

- `safe`: only `safe` commands are allowed.
- `write`: `safe` + `write` commands are allowed.
- `dangerous`: `safe` + `write` + potentially dangerous commands (with additional gate).

`OTERMINUS_ALLOW_DANGEROUS`:

- must be `true` **and** mode must be `dangerous` for dangerous operations to pass policy.

## Path scope restriction

`OTERMINUS_ALLOWED_ROOTS` can restrict path operands to an allowlisted set of root directories.

If a path operand resolves outside allowed roots, validation rejects the command.

## Confirmation strength

Confirmation is stricter for higher-risk or less deterministic flows:

- standard confirmation for normal safe/write structured flows
- strong confirmation for dangerous risk
- very strong confirmation for experimental mode
