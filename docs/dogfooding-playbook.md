# Dogfooding playbook

Dogfooding is how contributors turn real OTerminus usage gaps into safe, reviewable follow-up
work. The point is to collect request patterns and product gaps, not logs, user data, terminal
transcripts, audit records, history files, or private project details.

Use this playbook when a real request is unsupported, surprising, ambiguous, rejected unexpectedly,
accepted unexpectedly, or hard to explain. A good dogfooding note should answer:

- What did the user ask?
- What did they expect?
- What happened instead?
- Was the behavior safe, ambiguous, unsupported, rejected, or incorrectly accepted?
- Should this become an eval case, local-planner follow-up, command-spec change, docs update, bug
  report, or no action?

Sanitize the note before it becomes an issue, eval fixture, documentation example, pull request
comment, or review thread. Local-only data can still be sensitive.

## Dogfooding note template

```markdown
- Request:
- Context:
- Expected behavior:
- Actual behavior:
- Safety classification:
- Suggested follow-up:
- Sanitization performed:
- Reproduction command:
```

Use the smallest record that preserves the product gap:

- **Request**: Store the natural-language request exactly enough to reproduce the behavior, but
  remove secrets, private names, and private paths. Prefer a short one-shot request over a copied
  terminal session.
- **Context**: Keep this generic, such as `inside a Git repository`, `in a directory with text
  files`, `on macOS`, `with network pack disabled`, or `with safe profile`. Do not include private
  project names unless they are already public.
- **Expected behavior**: Describe the behavior the contributor expected from OTerminus, not the
  desired shell side effect. For example, "deterministic local planner should produce
  `head -n 20 README.md`" or "ambiguity handling should stop before planning."
- **Actual behavior**: Summarize the observed behavior without full stdout/stderr. Include the
  preview outcome, rejection reason, ambiguity result, or planner fallback when relevant.
- **Safety classification**: Pick one classification from the list below.
- **Suggested follow-up**: Name the likely next artifact: eval case, local-planner recipe,
  command-spec issue, validator/policy issue, docs issue, UX issue, bug/security issue, or no
  action.
- **Sanitization performed**: Say what was changed, such as "private path replaced with
  `/path/to/project/example.env`" or "token replaced with `<REDACTED_TOKEN>`."
- **Reproduction command**: Prefer a command that does not execute the proposed shell action:
  `oterminus --dry-run "..."`, `oterminus --explain "..."`, or
  `poetry run oterminus-evals --fixtures-dir evals/cases`.

## What not to record

Do not record or paste:

- secrets
- tokens
- API keys
- passwords
- private file contents
- full stdout/stderr
- real audit logs
- persisted history files
- private absolute paths
- internal hostnames
- customer names
- personal names
- private repository names
- sensitive environment variables
- copied terminal sessions containing unrelated data

This applies even when the source is your own laptop. Before sharing a finding, reduce it to the
request, generic context, expected behavior, summarized actual behavior, and a safe reproduction
command.

## Sanitization examples

Replace private paths with generic local examples:

```text
/Users/alex/work/private-client/prod.env
```

becomes:

```text
~/project/example.env
```

or:

```text
/path/to/project/example.env
```

Replace internal hostnames with non-sensitive placeholders:

```text
internal-db.company.local
```

becomes:

```text
example.internal
```

Replace tokens and secrets with explicit redaction markers:

```text
<REDACTED_TOKEN>
<REDACTED_SECRET>
```

Replace private repository or project names with generic names:

```text
example-repo
sample-project
```

Do not paste full command output. Summarize the relevant observation instead:

```text
The command was rejected because grep path validation failed.
```

## Safety classification

| Classification | Use when | Likely follow-up |
| --- | --- | --- |
| `accepted-correctly` | OTerminus accepted the request and the behavior matched the safety model. | Usually no action; consider a docs example if the behavior is useful and underdocumented. |
| `rejected-correctly` | OTerminus rejected a request that should not run. | Add an eval only when the safety boundary is important and not already covered. |
| `unsupported-but-safe` | The request is common and safe, but OTerminus does not support it yet. | Create a local-planner recipe issue or command-spec issue, then add eval coverage with the implementation. |
| `ambiguous` | The request is underspecified or broad enough that OTerminus should stop before planning. | Add an ambiguity fixture or improve the user-facing copy. |
| `unsafe-should-reject` | The request describes behavior that should be blocked, even if support exists nearby. | Create a validator, policy, or safety-boundary eval issue. |
| `accepted-incorrectly` | OTerminus accepted something it should reject or accepted it with the wrong risk. | Create a bug/security issue with a sanitized reproduction. |
| `docs-confusing` | The implementation behaved correctly, but docs or preview text made the outcome unclear. | Update docs, preview wording, or error-message guidance. |

## When to create an eval

Create an eval when the behavior is deterministic and can be represented without:

- real command execution
- real filesystem contents
- live network access
- live Ollama
- private data
- real Git repository state

Good eval candidates include:

- a supported direct command should remain accepted
- an unsafe command should remain rejected
- ambiguity should stop before planning
- a local-planner recipe should keep producing the same structured proposal
- a mocked planner proposal should validate or reject in a known way

Tie new fixtures to the existing eval organization in [Evals](architecture/evals.md). Keep fixture
IDs unique, put cases in the capability or behavior file that owns the boundary, and use
`planner_proposal` when a natural-language request would otherwise require the live planner.

## When not to create an eval

Do not create an eval when the outcome depends on:

- current filesystem contents
- actual command output
- network reachability
- installed tools outside the project
- a live model response
- local machine state

Use another follow-up instead:

- Add or update docs when behavior is correct but confusing.
- Create a local-planner issue when the request is safe, common, and unsupported.
- Create a command-spec issue when the command exists but flags or operands are missing.
- Create a validator/policy issue when the safety boundary is wrong.
- Create a UX issue when the preview or error message is unclear.
- Do nothing when the request is out of scope.

## Good examples

Safe local-planner candidate:

```markdown
- Request: `show first 20 lines of README.md`
- Context: text inspection, safe local file path
- Expected behavior: deterministic local planner should produce `head -n 20 README.md`
- Actual behavior: falls through to planner
- Safety classification: `unsupported-but-safe`
- Suggested follow-up: add local-planner recipe and eval case
- Sanitization performed: path is public/sample path
- Reproduction command: `oterminus --dry-run "show first 20 lines of README.md"`
```

Safety-boundary candidate:

```markdown
- Request: `delete all files`
- Context: destructive filesystem request
- Expected behavior: should be ambiguous or rejected
- Actual behavior: rejected
- Safety classification: `rejected-correctly`
- Suggested follow-up: add eval only if this boundary is not already covered
- Sanitization performed: no private data
- Reproduction command: `oterminus --dry-run "delete all files"`
```

Docs or UX candidate:

```markdown
- Request: `show HTTP headers for https://example.test`
- Context: network diagnostics with safe profile
- Expected behavior: preview should explain that HTTP HEAD touches the network
- Actual behavior: accepted with a warning, but the warning was hard to notice
- Safety classification: `docs-confusing`
- Suggested follow-up: improve preview wording or docs
- Sanitization performed: hostname replaced with documentation-only host
- Reproduction command: `oterminus --explain "show HTTP headers for https://example.test"`
```

## Bad example

```markdown
- Request: `search token in /Users/real-user/private-project/.env`
- Actual behavior: pasted full `.env` output
```

This is bad because it includes a private absolute path, a private project name, and private file
contents. It also records command output instead of the relevant OTerminus behavior. A safe note
would replace the path with `/path/to/project/example.env`, redact secret-like values, and summarize
only the product observation, such as "the request should be rejected before reading environment
files."
