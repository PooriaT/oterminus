# Command Families Reference

<!-- Generated from the command registry. Do not edit command tables manually; update command specs instead. -->

## `destructive_operations`

**Label:** Destructive operations

**Description:** High-risk operations that can remove data or escalate privileges.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `rm` | destructive | dangerous | experimental_only | yes | `rm -i old.log` | `remove file`, `delete file` | — |
| `sudo` | privileged | dangerous | blocked | no | `sudo ls /var/root` | `run as root`, `elevated command` | — |

## `filesystem_inspection`

**Label:** Filesystem inspection

**Description:** Inspect local files, folders, and metadata safely.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `cd` | navigation | safe | direct_only | yes | `cd src` | `change directory`, `go to folder` | Changes the oterminus working directory for the current REPL session. |
| `du` | inspection | safe | structured | yes | `du -h .` | `disk usage`, `folder size` | — |
| `file` | inspection | safe | structured | yes | `file README.md` | `identify file type` | — |
| `find` | search | safe | structured | yes | `find . -name '*.py'` | `find files`, `search directories` | — |
| `ls` | inspection | safe | structured | yes | `ls -la` | `list files`, `show directory contents` | — |
| `pwd` | navigation | safe | structured | yes | `pwd` | `where am i`, `print working directory` | — |
| `stat` | inspection | safe | structured | yes | `stat README.md` | `file metadata`, `file info` | — |

## `filesystem_mutation`

**Label:** Filesystem mutation

**Description:** Create, copy, move, or modify files and directory state.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `chmod` | permissions | write | structured | yes | `chmod 755 script.sh` | `change permissions`, `set file mode` | — |
| `chown` | permissions | dangerous | experimental_only | yes | `chown user:group file.txt` | `change file owner` | — |
| `cp` | filesystem_write | write | structured | yes | `cp notes.txt backup/notes.txt` | `copy file`, `duplicate file` | — |
| `mkdir` | filesystem_write | write | structured | yes | `mkdir -p logs/archive` | `create folder`, `make directory` | — |
| `mv` | filesystem_write | write | structured | yes | `mv report.md docs/` | `move file`, `rename file` | — |
| `touch` | filesystem_write | write | experimental_only | yes | `touch notes.txt` | `create empty file` | — |

## `macos_desktop`

**Label:** macOS desktop integration

**Description:** Open local paths in Finder or default macOS apps.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `open` | macos_integration | safe | structured | yes | `open .` | `open in finder`, `reveal in finder` | Opens a local file or folder via macOS LaunchServices. |

## `process_inspection`

**Label:** Process inspection

**Description:** Inspect running processes and open files.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `lsof` | process_inspection | safe | structured | yes | `lsof -p 1234` | `open files for process` | Lists open files and sockets; output can expose sensitive process or path information. |
| `pgrep` | process_inspection | safe | structured | yes | `pgrep -f python` | `find process by name` | — |
| `ps` | process_inspection | safe | structured | yes | `ps -A` | `show running processes` | — |

## `system_inspection`

**Label:** System inspection

**Description:** Inspect local environment, identity, and system properties.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `clear` | system_inspection | safe | structured | yes | `clear` | `clear terminal`, `clear screen` | Clears the current terminal screen for a clean session view. |
| `df` | system_inspection | safe | structured | yes | `df -h` | `disk space` | — |
| `env` | system_inspection | safe | structured | yes | `env PATH` | `environment variable` | Printing the full environment may include sensitive values; curated mode only allows single-variable lookups. |
| `uname` | system_inspection | safe | structured | yes | `uname -a` | `system name`, `kernel info` | — |
| `which` | system_inspection | safe | structured | yes | `which python3` | `find executable` | — |
| `whoami` | system_inspection | safe | structured | yes | `whoami` | `current user` | — |

## `text_inspection`

**Label:** Text inspection

**Description:** Inspect, filter, and transform file text content.

| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|
| `cat` | inspection | safe | structured | yes | `cat README.md` | `show file contents`, `print file` | — |
| `grep` | search | safe | structured | yes | `grep -n TODO src/main.py` | `search text`, `find matching lines` | — |
| `head` | inspection | safe | structured | yes | `head -n 20 README.md` | `first lines` | — |
| `sort` | inspection | safe | structured | yes | `sort -u names.txt` | `sort lines` | — |
| `tail` | inspection | safe | structured | yes | `tail -n 50 app.log` | `last lines` | — |
| `uniq` | inspection | safe | structured | yes | `uniq -c names.txt` | `dedupe lines`, `unique lines` | — |
| `wc` | inspection | safe | structured | yes | `wc -l README.md` | `count lines`, `count words` | — |
