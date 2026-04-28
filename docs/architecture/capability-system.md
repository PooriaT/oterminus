# Capability System

OTerminus groups commands into workflow capabilities rather than exposing unrestricted shell behavior.

## Why capability-first

- keeps planner context compact and stable
- enables policy and UX at workflow level
- avoids unbounded command/flag surfaces
- improves explainability for contributors and users

## Capability metadata

Each command spec includes:

- `capability_id`
- `capability_label`
- `capability_description`
- command examples and natural-language aliases

Capability summaries are derived from merged registry metadata and reused for prompts and REPL discovery.

## Current capability domains

- `filesystem_inspection`
- `filesystem_mutation`
- `text_inspection`
- `process_inspection`
- `system_inspection`
- `macos_desktop`
- `destructive_operations`

See [reference capability map](../reference/capability-map.md).
