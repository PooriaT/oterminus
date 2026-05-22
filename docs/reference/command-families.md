# Command Families Reference

<!-- Generated from the command registry. Do not edit command tables manually; update command specs instead. -->

## `archive_inspection`

**Label:** Archive inspection

**Description:** Inspect archives and extract them only to explicit destinations.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `tar` | archive_inspection | all | safe | structured | yes | `tar -tf archive.tar`<br>`tar -xf archive.tar -C out` | `list tar archive`, `inspect tar archive`, `show tar contents`, `list archive contents`, `extract tar archive`, `extract archive into destination` | Supports read-only tar archive listing and guarded extraction with an explicit destination.<br>Tar extraction is write-risk and can write or overwrite files in the destination.<br>Archive creation, compression flags, path transforms, extraction without -C, and arbitrary tar options are not supported. |
| `unzip` | archive_inspection | all | safe | structured | yes | `unzip -l archive.zip`<br>`unzip archive.zip -d out` | `list zip archive`, `inspect zip archive`, `show zip contents`, `show what is inside zip`, `extract zip archive`, `unzip archive into destination` | Supports read-only zip archive listing and guarded extraction with an explicit destination.<br>Zip extraction is write-risk and can write or overwrite files in the destination.<br>Extraction without -d, overwrite flags, password handling, and arbitrary unzip options are not supported. |

## `destructive_operations`

**Label:** Destructive operations

**Description:** High-risk operations that can remove data or escalate privileges.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `rm` | destructive | all | dangerous | experimental_only | yes | `rm -i old.log` | `remove file`, `delete file` | — |
| `sudo` | privileged | all | dangerous | blocked | no | `sudo ls /var/root` | `run as root`, `elevated command` | — |

## `filesystem_inspection`

**Label:** Filesystem inspection

**Description:** Inspect local files, folders, and metadata safely.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `cd` | navigation | all | safe | direct_only | yes | `cd src` | `change directory`, `go to folder` | Changes the oterminus working directory for the current REPL session. |
| `du` | inspection | all | safe | structured | yes | `du -h .` | `disk usage`, `folder size` | — |
| `file` | inspection | all | safe | structured | yes | `file README.md` | `identify file type` | — |
| `find` | search | all | safe | structured | yes | `find . -name '*.py'` | `find files`, `search directories` | — |
| `ls` | inspection | all | safe | structured | yes | `ls -la` | `list files`, `show directory contents` | — |
| `pwd` | navigation | all | safe | structured | yes | `pwd` | `where am i`, `print working directory` | — |
| `stat` | inspection | all | safe | structured | yes | `stat README.md` | `file metadata`, `file info` | — |

## `filesystem_mutation`

**Label:** Filesystem mutation

**Description:** Create, copy, move, or modify files and directory state.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `chmod` | permissions | all | write | structured | yes | `chmod 755 script.sh` | `change permissions`, `set file mode` | — |
| `chown` | permissions | all | dangerous | experimental_only | yes | `chown user:group file.txt` | `change file owner` | — |
| `cp` | filesystem_write | all | write | structured | yes | `cp notes.txt backup/notes.txt` | `copy file`, `duplicate file` | — |
| `mkdir` | filesystem_write | all | write | structured | yes | `mkdir -p logs/archive` | `create folder`, `make directory` | — |
| `mv` | filesystem_write | all | write | structured | yes | `mv report.md docs/` | `move file`, `rename file` | — |
| `touch` | filesystem_write | all | write | experimental_only | yes | `touch notes.txt` | `create empty file` | — |

## `git_inspection`

**Label:** Git inspection

**Description:** Read-only inspection of local Git repository state.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `git` | git_inspection | all | safe | structured | yes | `git status --short`<br>`git branch --show-current`<br>`git log --oneline -n 5`<br>`git diff --stat`<br>`git diff --name-only` | `git status`, `short git status`, `what branch am i on`, `show current git branch`, `show recent git commits`, `show git diff summary`, `show changed files`, `inspect git repo` | Only read-only Git inspection operations are supported in curated mode. |

## `macos_desktop`

**Label:** macOS desktop integration

**Description:** Open local paths in Finder or default macOS apps.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `open` | macos_integration | darwin | safe | structured | yes | `open .` | `open in finder`, `reveal in finder` | Opens a local file or folder via macOS LaunchServices. |

## `process_inspection`

**Label:** Process inspection

**Description:** Inspect running processes and open files.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `lsof` | process_inspection | all | safe | structured | yes | `lsof -p 1234` | `open files for process` | Lists open files and sockets; output can expose sensitive process or path information. |
| `pgrep` | process_inspection | all | safe | structured | yes | `pgrep -f python` | `find process by name` | — |
| `ps` | process_inspection | all | safe | structured | yes | `ps -A` | `show running processes` | — |

## `system_inspection`

**Label:** System inspection

**Description:** Inspect local environment, identity, and system properties.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `clear` | system_inspection | all | safe | structured | yes | `clear` | `clear terminal`, `clear screen` | Clears the current terminal screen for a clean session view. |
| `df` | system_inspection | all | safe | structured | yes | `df -h` | `disk space` | — |
| `env` | system_inspection | all | safe | structured | yes | `env PATH` | `environment variable` | Printing the full environment may include sensitive values; curated mode only allows single-variable lookups. |
| `uname` | system_inspection | all | safe | structured | yes | `uname -a` | `system name`, `kernel info` | — |
| `which` | system_inspection | all | safe | structured | yes | `which python3` | `find executable` | — |
| `whoami` | system_inspection | all | safe | structured | yes | `whoami` | `current user` | — |

## `text_inspection`

**Label:** Text inspection

**Description:** Inspect, filter, and transform file text content.

| Command | Category | Platforms | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|
| `cat` | inspection | all | safe | structured | yes | `cat README.md` | `show file contents`, `print file` | — |
| `grep` | search | all | safe | structured | yes | `grep -n TODO src/main.py` | `search text`, `find matching lines` | — |
| `head` | inspection | all | safe | structured | yes | `head -n 20 README.md` | `first lines` | — |
| `sort` | inspection | all | safe | structured | yes | `sort -u names.txt` | `sort lines` | — |
| `tail` | inspection | all | safe | structured | yes | `tail -n 50 app.log` | `last lines` | — |
| `uniq` | inspection | all | safe | structured | yes | `uniq -c names.txt` | `dedupe lines`, `unique lines` | — |
| `wc` | inspection | all | safe | structured | yes | `wc -l README.md` | `count lines`, `count words` | — |
