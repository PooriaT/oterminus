# Supported Workflows

OTerminus currently focuses on curated local workflows grouped by capability.

## Filesystem inspection

Examples:

- list files and directories
- inspect metadata and disk usage
- navigate working directory

Representative families: `cd`, `ls`, `pwd`, `find`, `du`, `stat`, `file`.

## Filesystem mutation

Examples:

- create directories/files
- copy/move files
- adjust permissions

Representative families: `mkdir`, `cp`, `mv`, `chmod`, `touch`, `chown`.

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
- inspect disk space

Representative families: `clear`, `whoami`, `uname`, `which`, `env`, `df`.

## macOS desktop integration

Example:

- open local files/folders in Finder/apps

Representative family: `open`.

## Destructive operations

High-risk families are explicitly tracked and heavily constrained.

Representative families: `rm`, `sudo`.

See [command families reference](../reference/command-families.md) for maturity/risk details.
