---
title: OTerminus
slug: /
description: Local, safety-first terminal assistance with structured proposals, policy gates, previews, and explicit confirmation.
---

# OTerminus

<div class="landingHero">
  <p class="landingEyebrow">Local · structured-first · safety-first</p>
  <p class="landingTagline">
    OTerminus is a local, safety-first terminal assistant that turns natural-language requests into
    one proposed shell action, previews it, validates it, and asks before running.
  </p>
  <p class="landingLead">
    It is for developers and terminal users who want help with common Unix-like workflows without
    handing execution authority to an LLM or opening the door to arbitrary shell generation.
  </p>
  <div class="landingCtas">
    <a class="button button--primary button--lg" href="#get-started">Get started</a>
    <a class="button button--secondary button--lg" href="#install">Install</a>
    <a class="button button--secondary button--lg" href="product/supported-workflows">Supported workflows</a>
    <a class="button button--secondary button--lg" href="architecture/overview">Architecture overview</a>
    <a class="button button--secondary button--lg" href="https://github.com/PooriaT/oterminus">GitHub</a>
  </div>
</div>

## What OTerminus does

OTerminus sits between your request and your shell. It recognizes direct commands, routes specific
natural-language requests to supported capabilities, asks a local Ollama model to produce structured
proposals when planning is needed, validates the resulting command, renders a preview, and requires
explicit confirmation by default.

<div class="landingCardGrid">
  <div class="landingCard">
    <h3>Local LLM planning</h3>
    <p>Natural-language planning uses Ollama locally. PyPI installation gives you the CLI; it does not install Ollama or a model.</p>
  </div>
  <div class="landingCard">
    <h3>Direct command detection</h3>
    <p>Known shell-like commands can bypass natural-language planning, but they still go through validation and policy checks.</p>
  </div>
  <div class="landingCard">
    <h3>Structured proposals first</h3>
    <p>Supported command families use typed proposal data that OTerminus renders deterministically instead of trusting raw model text.</p>
  </div>
  <div class="landingCard">
    <h3>Validation and policy gates</h3>
    <p>Risk levels, platform support, command-family rules, and policy mode decide whether a proposal is allowed, warned, or rejected.</p>
  </div>
  <div class="landingCard">
    <h3>Preview before execution</h3>
    <p>OTerminus shows the proposed command, risk, warnings, and rejections before anything runs.</p>
  </div>
  <div class="landingCard">
    <h3>Confirmation by default</h3>
    <p>Execution normally waits for explicit confirmation. Experimental proposals and higher-risk operations require stronger confirmation.</p>
  </div>
  <div class="landingCard">
    <h3>Config, doctor, and evals</h3>
    <p>Use local configuration, <code>oterminus doctor</code>, generated references, and packaged evals to inspect and verify behavior.</p>
  </div>
</div>

## Install {#install}

For normal CLI use, prefer `pipx` so OTerminus and its dependencies stay isolated from your system
Python environment.

```bash
pipx install oterminus
oterminus --version
oterminus doctor
oterminus
```

If `pipx` is not available, install from PyPI with pip instead:

```bash
python -m pip install oterminus
```

Requirements include Python 3.13+, a macOS or Unix-like POSIX terminal environment, and
[Ollama](https://ollama.com/) for natural-language planning. Direct commands and some deterministic
utility paths may be usable without a live model, but first-time natural-language usage depends on
Ollama being installed, running, and having a local model available.

## Get started {#get-started}

1. Install OTerminus with `pipx install oterminus`.
2. Run `oterminus doctor` to check the package, platform, config paths, command registry, and Ollama readiness.
3. Make sure Ollama is installed and running before relying on natural-language planning.
4. Start the interactive REPL with `oterminus`.
5. Try direct commands or specific, safe natural-language requests.
6. Use `--dry-run` and `--explain` before trusting a new command pattern.

```bash
oterminus "show disk usage for this folder"
oterminus --dry-run "find large files here"
oterminus --explain "find processes matching python"
oterminus "ls -lah"
```

The first bare interactive launch may offer a configuration wizard for local safety and privacy
preferences. One-shot commands, `--dry-run`, `--explain`, `doctor`, `version`, `completion`, and
`config` commands do not trigger onboarding.

## How the safety model works

OTerminus treats LLM output as a proposal, not execution authority.

- Direct commands are detected before planning, but still go through validation and policy.
- Natural-language requests go through the local LLM planner only after routing and ambiguity checks.
- Ambiguous natural-language requests are blocked before planning or execution.
- Structured proposals are validated and rendered deterministically from typed fields.
- Unsupported commands, unsafe flag combinations, platform-incompatible commands, and blocked capabilities are rejected.
- Experimental proposals require stronger confirmation and do not qualify for safe auto-execute.
- LLM-planned commands cannot bypass validation, policy gates, preview, or confirmation.

See [Request lifecycle](architecture/request-lifecycle.md), [Routing and planning](architecture/routing-and-planning.md), and
[Validation and policy](architecture/validation-and-policy.md) for the full flow.

## Supported workflows

OTerminus is capability-first, not a fully general shell copilot. Current documentation and the
command registry cover these workflow categories:

- filesystem inspection and constrained filesystem mutation;
- text inspection and search;
- process inspection;
- read-only Git inspection;
- constrained network diagnostics;
- archive inspection, creation, and extraction with explicit paths and guarded rules;
- system and manual-page inspection;
- curated project-health operations such as tests, lint, format checks, docs builds, and evals.

Review the [Supported workflows](product/supported-workflows.md) guide and generated
[Command families reference](reference/command-families.md) before assuming a command family or flag set
is supported.

## Where to go next

<div class="landingLinkGrid">
  <a href="product/what-is-oterminus"><strong>What is OTerminus?</strong><span>Product principles and typical journey.</span></a>
  <a href="product/user-guide"><strong>User guide</strong><span>Install, doctor, REPL, one-shot, dry-run, and explain.</span></a>
  <a href="product/supported-workflows"><strong>Supported workflows</strong><span>Capabilities and examples that are currently in scope.</span></a>
  <a href="reference/config"><strong>Configuration reference</strong><span>Environment variables, config file behavior, policy, audit, and history settings.</span></a>
  <a href="architecture/request-lifecycle"><strong>Request lifecycle</strong><span>Direct detection, ambiguity handling, planning, validation, preview, and execution.</span></a>
  <a href="architecture/routing-and-planning"><strong>Routing and planning</strong><span>How natural-language requests become structured proposals.</span></a>
  <a href="architecture/validation-and-policy"><strong>Validation and policy</strong><span>Risk, rejections, warnings, and policy boundaries.</span></a>
  <a href="architecture/evals"><strong>Evals</strong><span>How behavior is checked with deterministic fixtures.</span></a>
  <a href="https://github.com/PooriaT/oterminus"><strong>GitHub repository</strong><span>Source code, issues, changelog, and contribution history.</span></a>
</div>

## Build and preview docs locally

```bash
poetry install --with dev
cd website
npm ci
npm run start
npm run build
npm run typecheck
```

See the [contributor workflow](contributing.md) for the complete local lint, format, test, and docs
checklist.
