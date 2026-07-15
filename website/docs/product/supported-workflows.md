# Supported Workflows

OTerminus currently focuses on curated local workflows grouped by capability.

Direct commands for supported families can be detected locally, so forms such as `ls -lah` or
`git status --short` do not need the LLM planner. Natural-language requests normally use the
configured LLM model to propose a structured command in the required schema, then OTerminus
validates, previews, confirms, and executes only if accepted. If the model returns invalid proposal
JSON after the bounded repair attempt, the request is rejected safely.

The optional `deterministic_shortcut` layer is limited to fixed zero-argument utility requests such
as current-directory and clear-screen requests. It is not broad natural-language support.

## Filesystem inspection

Examples:

- list files and directories
- inspect metadata and disk usage
- navigate working directory

Representative families: `cd`, `ls`, `pwd`, `find`, `du`, `stat`, `file`.

Structured `find` is read-only and supports one starting path plus a curated predicate subset: `-name <pattern>`, `-type f|d`, `-maxdepth <0-20>`, `-mtime -<days>`, and `-size +<bytes>c`. Planner arguments use `entry_type` (`file` or `directory`), bounded `max_depth`, `modified_within_days`, and `size_greater_than_bytes`; requested sizes are rendered as exact bytes, for example 100 MiB as `104857600`. Rendering is deterministic, checks allowed-root policy only against the starting path, keeps name patterns literal argv values, and never appends `-print`. Mutating actions (`-delete`, `-exec*`, `-ok*`), output-file actions, Boolean expression trees, permission/owner/group predicates, newer-than predicates, pruning/quit, and symlink traversal flags are unsupported.

## Filesystem mutation

Examples:

- create directories/files
- copy/move files
- adjust permissions

Representative families: `mkdir`, `cp`, `mv`, `chmod`, `touch`, `chown`.

Structured `touch` supports exactly `touch <one-explicit-local-path>`. It is write-risk, requires normal confirmation, never qualifies for safe auto-execute, and creates the file when missing or updates timestamps when the target already exists. Flags, multiple targets, broad roots such as `/`, `.`, `..`, `~`, URLs, wildcards, shell fragments, and timestamp/reference options are rejected; configured allowed-root restrictions still apply.

## Text inspection

Examples:

- read file content
- search lines/patterns
- summarize line/word counts

Representative families: `cat`, `head`, `tail`, `grep`, `wc`, `sort`, `uniq`.

## Process inspection

Examples:

- list processes
- match process names
- inspect open files/sockets

Representative families: `ps`, `pgrep`, `lsof`.

## System inspection

Examples:

- inspect user/system identity
- inspect environment variable values (single variable)
- inspect local manual pages for commands or sections, such as `show manual for ls` or
  `show manual section 5 for crontab`
- inspect disk space

Representative families: `clear`, `whoami`, `uname`, `which`, `env`, `man`, `df`.

## Network diagnostics

Examples:

- ping a host with a fixed count
- show HTTP headers for an HTTP(S) URL
- look up DNS records

Representative families: `ping`, `curl`, `dig`, `nslookup`.

These commands contact external hosts and may reveal network metadata. Mutating HTTP methods,
secret headers, cookies, downloads, scanning, SSH/SCP, nmap, wget, netcat, sudo network commands,
and arbitrary network automation are unsupported.

## macOS desktop integration

Example:

- open local files/folders in Finder/apps

Representative family: `open`.

## Project health

Examples:

- run tests
- check linting
- check formatting without rewriting files
- build docs
- run eval fixtures

Representative family: `project_health`.

Project-health requests are natural-language planner requests. Direct `poetry run ...` input is not
accepted as project-health support. Accepted project-health proposals render only to curated
`poetry run ...` operations, may execute local project code or tooling, and always require preview
plus explicit confirmation.

## Destructive operations

High-risk families are explicitly tracked and heavily constrained.

Representative families: `rm`, `sudo`.

See [command families reference](../reference/command-families.md) for maturity/risk details.
