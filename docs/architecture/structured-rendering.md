# Structured Rendering

Structured rendering means OTerminus executes typed command-family arguments rendered by Python, rather than trusting arbitrary shell strings.

## Flow

1. proposal contains `mode=structured`, `command_family`, and typed `arguments`
2. arguments are validated against family-specific schemas
3. renderer builds deterministic `argv` and display command string
4. validator re-checks rendered output against policy/allowlists

## Benefits

- deterministic command output
- reduced prompt-injection surface
- predictable validation behavior
- cleaner diffs in eval fixtures

## Fallback path

When requests cannot be represented by structured schemas, OTerminus can fall back to experimental mode with stricter confirmation and validator constraints.

## Compatibility handling

Legacy raw-mode payloads are normalized to current structured/experimental modes during proposal validation.
