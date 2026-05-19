## Summary

- Describe what changed and why.
- If any checklist item is not applicable, write `N/A` in this PR description; do not remove checklist items.

## Type of change

- [ ] Bug fix
- [ ] Enhancement
- [ ] Documentation
- [ ] Refactor
- [ ] Test/eval change
- [ ] Chore/tooling
- [ ] Command-family/capability change

## Architecture invariants

- [ ] The model does not execute commands directly.
- [ ] User-facing execution still requires preview and explicit confirmation.
- [ ] Structured mode remains the preferred path for supported capabilities.
- [ ] Experimental mode remains constrained and is not used as a shortcut around registry/renderer design.
- [ ] Direct commands still go through validation and policy checks.
- [ ] Ambiguous natural-language requests do not proceed to planning or execution.
- [ ] Validator and policy responsibilities remain separate.
- [ ] Command support remains capability-first, not shell-manual-first.
- [ ] Autocomplete/discovery/help paths do not call Ollama or execute commands.
- [ ] Audit logging remains local-only and redaction/privacy expectations are preserved.

## Safety checklist

- [ ] No secrets, real tokens, real audit logs, or personal local paths were added to code, docs, fixtures, or tests.
- [ ] Risky behavior changes (execution, policy, validation, command routing, or planning) are explicitly called out in this PR.

## Tests and evals

- [ ] `poetry run ruff format --check .` passes.
- [ ] `poetry run ruff check .` passes.
- [ ] `poetry run pytest --cov=src/oterminus --cov-report=term-missing` passes.
- [ ] `poetry run oterminus-evals` passes when planner/router/validator/policy/structured rendering or command behavior changed.
- [ ] `poetry run mkdocs build --strict` passes.
- [ ] `poetry run python scripts/check_docs_links.py` passes if that script exists.

## Docs checklist

- [ ] `README.md` updated if landing-page behavior changed.
- [ ] `/docs` updated if behavior, architecture, command support, config, evals, policy, validation, or user-facing behavior changed.
- [ ] MkDocs navigation updated if docs pages were added, moved, or deleted.
- [ ] Generated command reference docs refreshed if command registry/specs changed.
- [ ] Docs changes are included in this PR (not follow-up work).
