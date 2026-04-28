# Architecture Overview

OTerminus processes each request through a layered local pipeline:

1. direct command detection
2. ambiguity guardrails
3. capability routing
4. planner proposal generation
5. structured parsing/rendering preference
6. validation + policy gating
7. preview + confirmation
8. execution + audit logging

The architecture is built for deterministic control surfaces around LLM output, not free-form shell execution.

## Key modules

- `cli.py`: orchestration, REPL, one-shot flow
- `direct_commands.py`: direct command detection
- `ambiguity.py`: inspect-first ambiguity blocking
- `router.py`: deterministic route category classification
- `planner.py`: LLM JSON proposal parse + normalization
- `structured_commands.py`: typed structured argument schemas + deterministic rendering
- `validator.py`: shape checks, allowlist enforcement, policy checks
- `executor.py`: subprocess execution plus `cd`/`clear` built-ins
- `audit.py`: local JSONL lifecycle logging
- `commands/*`: modular capability packs and command specs

See [request lifecycle](request-lifecycle.md) for end-to-end flow.
