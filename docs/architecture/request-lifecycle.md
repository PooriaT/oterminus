# Request Lifecycle

This is the central execution flow for OTerminus.

```mermaid
flowchart TD
  A[User input] --> B[Direct command detection]
  B --> C{Direct command?}
  C -->|yes| H[Validator]
  C -->|no| D[Ambiguity detection]
  D --> E{Ambiguous?}
  E -->|yes| E1[Show safer inspection options and stop]
  E -->|no| F[Capability router]
  F --> G[Planner]
  G --> G1[Structured proposal parsing / normalization]
  G1 --> R[Structured renderer when supported]
  R --> H[Validator]
  H --> I[Policy gate]
  I --> J[Preview renderer]
  J --> K{Run mode}
  K -->|dry-run/explain| K1[Skip execution]
  K -->|execute| L[User confirmation]
  L -->|cancel| L1[Stop]
  L -->|confirm| M[Executor]
  M --> N[Audit log event]
  H --> O[Evals/tests validate deterministic behavior]
```

## Stage details

### 1) User input

Input can be:

- natural language (`"find large files here"`)
- direct command (`"ls -lah"`)

### 2) Direct command detection

If input already looks like a supported command family invocation, OTerminus skips LLM planning and builds a direct proposal.

### 3) Ambiguity handling

For natural language, broad/destructive underspecified wording is blocked early and replaced with safer read-only inspection options.

### 4) Capability router

A deterministic router classifies the request into categories like `filesystem_inspect`, `filesystem_mutate`, `text_search`, `process_inspect`, etc.

### 5) Planner + parsing

Planner asks Ollama for JSON output and validates it against the `Proposal` schema.

Planner then prefers structured mode when command family + arguments can be represented deterministically.

### 6) Structured rendering

For supported families, Python renders final command strings/argv from typed arguments (instead of trusting raw shell text).

### 7) Validation and policy

Validator enforces:

- curated command-family allowlist
- operand/flag shape checks
- blocked operators/redirection/chaining
- path safety checks (including allowed roots)
- risk + policy mode compatibility

### 8) Preview and confirmation

OTerminus renders preview details (command, mode, risk, warnings/rejections).

Execution requires explicit confirmation. Experimental mode uses very-strong confirmation text.

### 9) Execution

Executor runs command argv via subprocess, with special local handling for `cd` and `clear`.

### 10) Audit logging

When enabled, OTerminus writes a JSONL event with request lifecycle fields (routing, mode, validation, confirmation, exit code, duration).

### 11) Evals and tests

Deterministic fixture evals and unit tests assert lifecycle invariants and prevent regressions.
