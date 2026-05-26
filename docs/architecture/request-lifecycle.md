# Request Lifecycle

This is the central execution flow for OTerminus. The order is deliberate: OTerminus detects direct
shell commands before applying natural-language ambiguity heuristics. Only non-direct,
natural-language requests are checked for ambiguity before capability routing and planner calls.

```mermaid
flowchart TD
  A[User input] --> A1{CLI diagnostics mode?}
  A1 -->|doctor| A2[Run doctor checks and exit]
  A1 -->|request| B[Direct command detection]
  B --> C{Direct command?}
  C -->|yes| C1[Build direct proposal]
  C -->|no| D[Ambiguity detection]
  D --> E{Ambiguous?}
  E -->|yes| E1[Show safer inspection options]
  E1 --> N
  E -->|no| F[Capability router]
  F --> G[Planner JSON proposal]
  G --> P[Parse Proposal schema]
  C1 --> P
  P --> S{Structured support suitable?}
  S -->|yes| S1[Structured mode: command_family + arguments]
  S1 --> R[Deterministic Python renderer]
  S -->|no| X1[Experimental mode: constrained command text]
  R --> H[Validator]
  X1 --> H
  H --> I[Policy gate]
  I --> J[Preview renderer]
  J --> K{Run mode}
  K -->|dry-run/explain| K1[Skip confirmation and execution]
  K1 --> N[Audit log event]
  K -->|execute| L[User confirmation]
  L -->|cancel| L1[Stop]
  L -->|confirm| M[Executor]
  M --> N[Audit log event]
  H --> O[Evals/tests validate deterministic behavior]
```

## Stage details

### 1) User input

Input can be:

- the explicit diagnostics command (`doctor`), which runs readiness checks and exits outside the
  normal request planning/execution lifecycle
- natural language (`"find large files here"`)
- direct command (`"ls -lah"`)

### 2) Direct command detection

Direct command detection runs before ambiguity detection. If input already looks like a supported
command family invocation, OTerminus skips LLM planning and builds a direct proposal. Examples such
as `chmod +x run.sh` and `rm -rf build` are not intercepted as ambiguous natural language.

Direct proposals still continue through proposal parsing, structured rendering when available,
validation, policy checks, preview, and confirmation in execute mode. In `--dry-run` or `--explain`
one-shot mode, direct proposals do not require Ollama if direct detection succeeds.

### 3) Ambiguity handling

Ambiguity detection runs only for non-direct natural-language requests. It looks for broad,
destructive, or underspecified wording such as “clean this folder”, “delete unnecessary files”, or
“repair permissions”. When such a request is ambiguous, OTerminus shows a short explanation and safe
read-only inspection alternatives.

Ambiguous requests stop before planner setup, planner calls, validation, confirmation prompts, and
execution. Nothing is executed, including in dry-run or explain mode. Their audit events use
`confirmation_result: "blocked_ambiguous"` and include the ambiguity reason plus suggested safe
options. They also record planner skip diagnostics with `planner_invoked: false`,
`planner_skipped: true`, and `planner_skip_reason: "ambiguity_blocked"`.

### 4) Capability router

A deterministic router classifies the request into categories like `filesystem_inspect`,
`filesystem_mutate`, `text_search`, `process_inspect`, etc.

### 5) Planner + parsing

Planner asks Ollama for JSON output and validates it against the `Proposal` schema. The schema
supports only two first-class modes: `structured` and `experimental`.

Planner and parser prefer structured mode when command family + arguments can be represented
deterministically. Experimental mode is used only when structured support is unavailable or
unsuitable for a constrained single-command proposal.

### 6) Structured or experimental proposal handling

For structured proposals, Python renders final command strings/argv from typed arguments instead of
trusting command text. Direct commands may also be normalized into structured arguments when a parser
is available. Experimental proposals may carry command text, but they remain constrained by parsing,
registry, validator, policy, preview, and stronger confirmation.

### 7) Validation and policy

Validator enforces:

- curated command-family allowlist
- operand/flag shape checks
- blocked operators/redirection/chaining
- path safety checks (including allowed roots)
- risk + policy mode compatibility

### 8) Preview and run mode

OTerminus renders preview details (command, mode, risk, warnings/rejections).

The normal execute mode requires explicit confirmation after a successful preview. Experimental mode
uses very-strong confirmation text. Failed validation or policy checks stop before execution.

One-shot `--dry-run` and `--explain` modes still use direct detection and, for specific
natural-language requests, planning, validation, policy checks, and preview rendering. Ambiguous
natural-language requests stop earlier in every run mode. Dry-run and explain intentionally skip
confirmation and execution after successful validation. The REPL `dry-run <request>` and
`explain <request>` built-ins provide the same inspection behavior inside an interactive session.

### 9) Execution

Executor runs command argv via subprocess, with special local handling for `cd` and `clear`.

### 10) Audit logging

When enabled, OTerminus writes a JSONL event with request lifecycle fields (routing, mode,
validation, confirmation, exit code, duration). Ambiguous requests record the ambiguity outcome and
`blocked_ambiguous` status without planner, validation, confirmation, or execution fields. Dry-run
and explain requests record skipped execution status instead of an execution exit code.

### 11) Evals and tests

Deterministic fixture evals and unit tests assert lifecycle invariants and prevent regressions.

## REPL history-aware commands in lifecycle terms

In REPL mode, `history`, `history <n>`, and `explain <history_id>` are local inspection commands
for the current process session and do not execute shell commands.

`rerun <history_id>` does not shortcut execution. It submits the original user input back into the
same request lifecycle described above, including ambiguity handling, planning/direct detection,
validation/policy, preview, and explicit execute confirmation.

- After routing, OTerminus attempts a deterministic local planner for a small set of unambiguous requests. If it matches, Ollama is skipped and the same validation/preview/confirmation flow continues.
