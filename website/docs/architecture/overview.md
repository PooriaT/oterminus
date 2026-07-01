# Architecture Overview

OTerminus processes each request through a layered local pipeline:

1. direct command detection
2. ambiguity guardrails
3. capability routing
4. optional governed deterministic shortcuts
5. LLM planner proposal generation for remaining natural-language requests
6. structured parsing/rendering preference
7. validation + policy gating
8. preview + confirmation
9. execution + audit logging

The architecture is built for deterministic control surfaces around LLM output, not free-form shell
execution. The model never executes commands directly; it can only propose JSON that OTerminus
parses, validates, previews, and confirms.

## Proposal mode model

OTerminus has two supported first-class proposal modes:

- **Structured mode** is the preferred normal path. A proposal carries `command_family` plus typed
  `arguments`; Python validates those arguments and renders the final command string and `argv`
  deterministically. Use this path whenever a capability has structured support.
- **Experimental mode** is a constrained fallback for single-command text that is allowed by the
  registry but not yet safely represented by structured arguments. It remains subject to shell-shape
  checks, allowlists, policy gates, preview, and stronger confirmation. It is not a shortcut around
  capability or renderer design.

Legacy `"mode": "raw"` payloads may be accepted only as internal parse-boundary compatibility and
are normalized before downstream handling. Raw is not a public or architectural proposal mode.

## Architecture invariants

- The model never executes commands directly.
- Direct commands are handled locally before natural-language ambiguity checks.
- Deterministic shortcuts are optional, tiny, and not a general natural-language planner.
- Structured mode is preferred for supported capabilities.
- Experimental mode is constrained and higher-friction.
- Validator and policy decisions are authoritative for every proposal.
- User confirmation is required before execution.
- Direct commands still go through validation, policy checks, preview, and confirmation.

## Key modules

- `cli.py`: orchestration, REPL, one-shot flow
- `direct_commands.py`: direct command detection
- `ambiguity.py`: inspect-first ambiguity blocking
- `router.py`: deterministic route category classification
- `deterministic_shortcuts.py`: governed zero-argument utility shortcuts
- `planner.py`: LLM JSON proposal parse + normalization
- `structured_commands.py`: typed structured argument schemas + deterministic rendering
- `validator.py`: shape checks, allowlist enforcement, policy checks
- `executor.py`: subprocess execution plus `cd`/`clear` built-ins
- `audit.py`: local JSONL lifecycle logging
- `commands/*`: modular capability packs and command specs

See [request lifecycle](request-lifecycle.md) for end-to-end flow.
