# Changelog

All notable user-facing changes to OTerminus are documented here.

## Unreleased

Use this section for changes merged after the next planned release section has been prepared.

### Added

### Changed

### Fixed

### Documentation

### Internal

## 0.1.3 - Unreleased

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
