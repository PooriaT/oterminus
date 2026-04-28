# Capability Map

Current capabilities and command families:

- `filesystem_inspection` — inspect local files, folders, and metadata
  - `cd`, `ls`, `pwd`, `find`, `du`, `stat`, `file`
- `filesystem_mutation` — create/copy/move/permission changes
  - `mkdir`, `cp`, `mv`, `chmod`, `touch`, `chown`
- `text_inspection` — inspect/search/transform text
  - `cat`, `head`, `tail`, `grep`, `wc`, `sort`, `uniq`
- `process_inspection` — inspect processes and open files
  - `ps`, `pgrep`, `lsof`
- `system_inspection` — inspect identity/system/env state
  - `clear`, `whoami`, `uname`, `which`, `env`, `df`
- `macos_desktop` — open local paths via macOS desktop integration
  - `open`
- `destructive_operations` — high-risk operations
  - `rm`, `sudo`

Capability metadata (descriptions, aliases, maturity summaries) is generated from command specs in the merged registry.
