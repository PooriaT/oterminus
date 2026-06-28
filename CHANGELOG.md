# Changelog

All notable user-facing changes to OTerminus are documented here.

## Unreleased

Use this section for changes merged after the next planned release section has been prepared.

### Added

### Changed

### Fixed

### Documentation

### Internal

## 0.1.4

Proposal-source simplification, LLM planner schema hardening, and architecture cleanup release.

### Added

- Added schema-constrained LLM planner behavior for Ollama-backed proposals.
- Added deterministic proposal-source terminology for direct commands, deterministic shortcuts,
  and LLM planner output.
- Added eval coverage for planner schema, repair, proposal-source lifecycle, and deterministic
  shortcut behavior.
- Added safe config `get`, `set`, and `reset` commands plus installed-package smoke coverage for
  config commands.
- Added safe manual-page lookup support for `man` topics.

### Changed

- Simplified the proposal architecture around direct commands and LLM-planned natural-language
  requests.
- Reduced deterministic natural-language handling to a small governed shortcut layer.
- Reframed local-planner behavior as deterministic shortcuts and removed obsolete local-planner
  code, fixtures, tests, and references.
- Persisted proposal origin in history records.
- Updated request lifecycle, routing/planning, eval, and contributor documentation to reflect the
  simplified architecture.
- Expanded CI and release validation to include installed-package smoke checks.

### Fixed

- Improved handling and diagnostics when a selected Ollama model returns JSON that does not satisfy
  the OTerminus proposal schema.
- Prevented model-specific schema failures from being worked around through broad deterministic
  phrase matching.
- Tightened auto-execute eligibility for legacy planner origins.
- Rejected invalid UTF-8 eval candidate files.

### Documentation

- Documented the direct-command vs LLM-planner proposal model.
- Documented when not to add deterministic shortcuts.
- Updated eval guidance for planner-path fixtures and deterministic shortcut coverage.
- Added dogfooding playbook guidance for collecting safe request examples.

### Internal

- Cleaned stale local-planner naming, fixtures, tests, and references after proposal-source
  simplification.
- Refactored app structure, terminal UI state handling, planner enum validation, and planner JSON
  repair trace output.

## 0.1.3

Configuration, onboarding, safety-default, and terminal-color release.

### Added

- Added validated persistent user configuration with schema-versioned config files.
- Added first-run onboarding for bare interactive launches, plus `oterminus config init` for
  rerunning the setup wizard.
- Added persistent onboarding state so accepted or declined onboarding does not repeatedly prompt.
- Added persistent terminal `color_mode` configuration with `auto`, `always`, and `never` modes.
- Added centralized semantic terminal styling through `TerminalStyle`.

### Changed

- Reloaded saved onboarding configuration before starting REPL services.
- Applied semantic terminal colors consistently across previews, diagnostics, discovery output,
  REPL prompts, and doctor output.
- Honored configured terminal color mode in doctor output, including redirected output behavior.

### Fixed

- Handled config initialization write failures cleanly while continuing with safe in-memory
  defaults.
- Avoided first-run onboarding prompts for one-shot direct commands, dry-run, explain, inspection,
  and special commands.
- Treated legacy config files without a schema version as completed onboarding in memory.

### Documentation

- Documented persistent configuration fields, onboarding behavior, and terminal color mode.

### Internal

- Added coverage for user config validation, onboarding state, color-mode resolution, semantic
  terminal styling, and CLI output color behavior.

## 0.1.2

Packaging, release validation, and public install workflow update.

### Added

- Added --version and version support for installed package verification.
- Added installed-package smoke validation to CI and release workflow.
- Added release-focused smoke evals for public install behavior.
- Added shell-level completion generation for zsh/bash/fish.

### Changed

- Improved doctor output for PyPI/pipx-installed users.

### Fixed

- Normalized collapsed source, config, workflow, and docs formatting.
- Reconciled planned project_health capability with user-facing docs and references.
- Aligned package classifiers with actual supported platforms.

### Documentation

- Updated README and docs for public PyPI/pipx installation.
- Added changelog and release checklist for 0.1.2+.

### Internal
