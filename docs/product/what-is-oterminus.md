# What is OTerminus?

OTerminus is a local terminal assistant that converts natural-language intent into one proposed terminal action at a time.

## Design intent

OTerminus is optimized for practical local workflows:

- inspect files and directories
- search and inspect text
- inspect running processes and system state
- apply constrained file mutations when policy allows

It intentionally does **not** try to emulate full shell freedom or all Unix command semantics.

## Product principles

- **Capability-first:** commands are grouped and controlled by workflow capability.
- **Structured-first:** when a command family is supported, arguments are validated and rendered deterministically.
- **Policy-gated:** risk levels and policy mode control what can run.
- **Confirm-before-execute:** execution requires explicit user confirmation.
- **Local-first:** model interaction is local via Ollama; logs are local JSONL when enabled.

## Typical user journey

1. User enters a request (natural language or a direct shell command).
2. OTerminus routes/plans and validates a proposal.
3. OTerminus prints a preview with risk and policy feedback.
4. User confirms (or cancels).
5. OTerminus executes and records an audit event.
