# Capability Map

<!-- Generated from the command registry. Do not edit command tables manually; update command specs instead. -->

| Capability ID | Label | Description | Commands | Platforms | Risk levels present | Maturity levels present | Notes |
|---|---|---|---|---|---|---|---|
| archive_inspection | Archive inspection | Inspect archives and extract them only to explicit destinations. | `tar`, `unzip` | all | safe | structured | Archive creation, compression flags, path transforms, extraction without -C, and arbitrary tar options are not supported.<br>Extraction without -d, overwrite flags, password handling, and arbitrary unzip options are not supported.<br>Supports read-only tar archive listing and guarded extraction with an explicit destination.<br>Supports read-only zip archive listing and guarded extraction with an explicit destination.<br>Tar extraction is write-risk and can write or overwrite files in the destination.<br>Zip extraction is write-risk and can write or overwrite files in the destination. |
| destructive_operations | Destructive operations | High-risk operations that can remove data or escalate privileges. | `rm`, `sudo` | all | dangerous | blocked, experimental_only | — |
| filesystem_inspection | Filesystem inspection | Inspect local files, folders, and metadata safely. | `cd`, `du`, `file`, `find`, `ls`, `pwd`, `stat` | all | safe | direct_only, structured | Changes the oterminus working directory for the current REPL session. |
| filesystem_mutation | Filesystem mutation | Create, copy, move, or modify files and directory state. | `chmod`, `chown`, `cp`, `mkdir`, `mv`, `touch` | all | dangerous, write | experimental_only, structured | — |
| git_inspection | Git inspection | Read-only inspection of local Git repository state. | `git` | all | safe | structured | Only read-only Git inspection operations are supported in curated mode. |
| macos_desktop | macOS desktop integration | Open local paths in Finder or default macOS apps. | `open` | darwin | safe | structured | Opens a local file or folder via macOS LaunchServices. |
| process_inspection | Process inspection | Inspect running processes and open files. | `lsof`, `pgrep`, `ps` | all | safe | structured | Lists open files and sockets; output can expose sensitive process or path information. |
| system_inspection | System inspection | Inspect local environment, identity, and system properties. | `clear`, `df`, `env`, `uname`, `which`, `whoami` | all | safe | structured | Clears the current terminal screen for a clean session view.<br>Printing the full environment may include sensitive values; curated mode only allows single-variable lookups. |
| text_inspection | Text inspection | Inspect, filter, and transform file text content. | `cat`, `grep`, `head`, `sort`, `tail`, `uniq`, `wc` | all | safe | structured | — |
