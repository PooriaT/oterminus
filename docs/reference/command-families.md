# Command Families Reference

<!-- Generated from the command registry. Do not edit command tables manually; update command specs instead. -->

## `archive_inspection`

**Label:** Archive operations

**Description:** Inspect archives, extract them only to explicit destinations, and create tar.gz/zip archives only from explicit source paths.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `tar` | archive_inspection | all | safe | structured | yes | no | `tar -tf archive.tar`<br>`tar -xf archive.tar -C out`<br>`tar -czf backup.tar.gz src` | `list tar archive`, `inspect tar archive`, `show tar contents`, `list archive contents`, `extract tar archive`, `extract archive into destination`, `create tar gz archive`, `create tar archive from explicit paths` | Supports read-only tar archive listing, guarded extraction with an explicit destination, and guarded tar.gz creation from explicit source paths.<br>Tar extraction is write-risk and can write or overwrite files in the destination.<br>Tar archive creation is write-risk and may overwrite an existing archive path depending on the underlying tar implementation.<br>Only tar -czf <archive_path> <source_paths...> is supported for tar.gz creation; broad roots, home roots, wildcards, path transforms, extraction without -C, and arbitrary tar options are not supported. |
| `unzip` | archive_inspection | all | safe | structured | yes | no | `unzip -l archive.zip`<br>`unzip archive.zip -d out` | `list zip archive`, `inspect zip archive`, `show zip contents`, `show what is inside zip`, `extract zip archive`, `unzip archive into destination` | Supports read-only zip archive listing and guarded extraction with an explicit destination.<br>Zip extraction is write-risk and can write or overwrite files in the destination.<br>Extraction without -d, overwrite flags, password handling, and arbitrary unzip options are not supported. |
| `zip` | archive_inspection | all | write | structured | yes | no | `zip -r backup.zip src` | `create zip archive`, `zip folder into archive`, `create zip archive from explicit paths` | Supports guarded zip archive creation from explicit source paths.<br>Zip archive creation is write-risk and may overwrite or update an existing archive path depending on the underlying zip implementation.<br>Only zip -r <archive_path> <source_paths...> is supported; broad roots, home roots, wildcards, encryption, passwords, split archives, append/update flags, deleting sources, network destinations, and arbitrary zip options are not supported. |

## `destructive_operations`

**Label:** Destructive operations

**Description:** High-risk operations that can remove data or escalate privileges.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `rm` | destructive | all | dangerous | experimental_only | yes | no | `rm -i old.log` | `remove file`, `delete file` | — |
| `sudo` | privileged | all | dangerous | blocked | no | no | `sudo ls /var/root` | `run as root`, `elevated command` | — |

## `filesystem_inspection`

**Label:** Filesystem inspection

**Description:** Inspect local files, folders, and metadata safely.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `cd` | navigation | all | safe | direct_only | yes | no | `cd src` | `change directory`, `go to folder` | Changes the oterminus working directory for the current REPL session. |
| `du` | inspection | all | safe | structured | yes | no | `du -h .` | `disk usage`, `folder size` | — |
| `file` | inspection | all | safe | structured | yes | no | `file README.md` | `identify file type` | — |
| `find` | search | all | safe | structured | yes | no | `find . -name '*.py'` | `find files`, `search directories` | — |
| `ls` | inspection | all | safe | structured | yes | no | `ls -la` | `list files`, `show directory contents` | — |
| `pwd` | navigation | all | safe | structured | yes | no | `pwd` | `where am i`, `print working directory` | — |
| `stat` | inspection | all | safe | structured | yes | no | `stat README.md` | `file metadata`, `file info` | — |

## `filesystem_mutation`

**Label:** Filesystem mutation

**Description:** Create, copy, move, or modify files and directory state.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `chmod` | permissions | all | write | structured | yes | no | `chmod 755 script.sh` | `change permissions`, `set file mode` | — |
| `chown` | permissions | all | dangerous | experimental_only | yes | no | `chown user:group file.txt` | `change file owner` | — |
| `cp` | filesystem_write | all | write | structured | yes | no | `cp notes.txt backup/notes.txt` | `copy file`, `duplicate file` | — |
| `mkdir` | filesystem_write | all | write | structured | yes | no | `mkdir -p logs/archive` | `create folder`, `make directory` | — |
| `mv` | filesystem_write | all | write | structured | yes | no | `mv report.md docs/` | `move file`, `rename file` | — |
| `touch` | filesystem_write | all | write | experimental_only | yes | no | `touch notes.txt` | `create empty file` | — |

## `git_inspection`

**Label:** Git inspection

**Description:** Read-only inspection of local Git repository state.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `git` | git_inspection | all | safe | structured | yes | no | `git status --short`<br>`git branch --show-current`<br>`git log --oneline -n 5`<br>`git diff --stat`<br>`git diff --name-only` | `git status`, `short git status`, `what branch am i on`, `show current git branch`, `show recent git commits`, `show git diff summary`, `show changed files`, `inspect git repo` | Only read-only Git inspection operations are supported in curated mode. |

## `macos_desktop`

**Label:** macOS desktop integration

**Description:** Open local paths in Finder or default macOS apps.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `open` | macos_integration | darwin | safe | structured | yes | no | `open .` | `open in finder`, `reveal in finder` | Opens a local file or folder via macOS LaunchServices. |

## `network_diagnostics`

**Label:** Network diagnostics

**Description:** Run constrained read-only diagnostics that contact external hosts.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `curl` | network_inspection | all | safe | structured | yes | yes | `curl -I https://example.com` | `show HTTP headers`, `http head request` | This command contacts external hosts and may reveal your IP address, DNS query, target host, or network metadata.<br>Only ping with a fixed count, HTTP HEAD requests, dig lookups, and nslookup lookups are supported.<br>POST/PUT/PATCH/DELETE, request bodies, arbitrary or secret-bearing headers, authorization, cookies, downloads, redirects that write files, scanning, traceroute, SSH/SCP, netcat, nmap, wget, sudo network commands, and arbitrary network shell commands are not supported. |
| `dig` | network_inspection | all | safe | structured | yes | yes | `dig example.com` | `dns lookup`, `get dns records` | This command contacts external hosts and may reveal your IP address, DNS query, target host, or network metadata.<br>Only ping with a fixed count, HTTP HEAD requests, dig lookups, and nslookup lookups are supported.<br>POST/PUT/PATCH/DELETE, request bodies, arbitrary or secret-bearing headers, authorization, cookies, downloads, redirects that write files, scanning, traceroute, SSH/SCP, netcat, nmap, wget, sudo network commands, and arbitrary network shell commands are not supported. |
| `nslookup` | network_inspection | all | safe | structured | yes | yes | `nslookup example.com` | `nslookup`, `dns lookup alternative` | This command contacts external hosts and may reveal your IP address, DNS query, target host, or network metadata.<br>Only ping with a fixed count, HTTP HEAD requests, dig lookups, and nslookup lookups are supported.<br>POST/PUT/PATCH/DELETE, request bodies, arbitrary or secret-bearing headers, authorization, cookies, downloads, redirects that write files, scanning, traceroute, SSH/SCP, netcat, nmap, wget, sudo network commands, and arbitrary network shell commands are not supported. |
| `ping` | network_inspection | all | safe | structured | yes | yes | `ping -c 4 example.com` | `ping host`, `check host responds` | This command contacts external hosts and may reveal your IP address, DNS query, target host, or network metadata.<br>Only ping with a fixed count, HTTP HEAD requests, dig lookups, and nslookup lookups are supported.<br>POST/PUT/PATCH/DELETE, request bodies, arbitrary or secret-bearing headers, authorization, cookies, downloads, redirects that write files, scanning, traceroute, SSH/SCP, netcat, nmap, wget, sudo network commands, and arbitrary network shell commands are not supported. |

## `process_inspection`

**Label:** Process inspection

**Description:** Inspect running processes and open files.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `lsof` | process_inspection | all | safe | structured | yes | no | `lsof -p 1234` | `open files for process` | Lists open files and sockets; output can expose sensitive process or path information. |
| `pgrep` | process_inspection | all | safe | structured | yes | no | `pgrep -f python` | `find process by name` | — |
| `ps` | process_inspection | all | safe | structured | yes | no | `ps -A` | `show running processes` | — |

## `project_health`

**Label:** Project health

**Description:** Curated project maintenance checks (tests, lint, format check, docs build, evals) modeled for explicit preview and confirmation.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `project_health` | developer_workflow | all | write | experimental_only | no | no | `project_health run_tests`<br>`project_health lint_check`<br>`project_health format_check`<br>`project_health build_docs`<br>`project_health run_evals` | `run project tests`, `check project formatting`, `run project lint`, `build project docs`, `run project evals` | Project health operations may execute local project code or tooling (for example via test suites, docs builds, and eval workflows).<br>Always preview and require explicit user confirmation before execution.<br>Only curated operations are in scope: run_tests, lint_check, format_check, build_docs, run_evals.<br>Arbitrary 'poetry run ...' and arbitrary shell execution are not supported. |

## `system_inspection`

**Label:** System inspection

**Description:** Inspect local environment, identity, and system properties.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `clear` | system_inspection | all | safe | structured | yes | no | `clear` | `clear terminal`, `clear screen` | Clears the current terminal screen for a clean session view. |
| `df` | system_inspection | all | safe | structured | yes | no | `df -h` | `disk space` | — |
| `env` | system_inspection | all | safe | structured | yes | no | `env PATH` | `environment variable` | Printing the full environment may include sensitive values; curated mode only allows single-variable lookups. |
| `uname` | system_inspection | all | safe | structured | yes | no | `uname -a` | `system name`, `kernel info` | — |
| `which` | system_inspection | all | safe | structured | yes | no | `which python3` | `find executable` | — |
| `whoami` | system_inspection | all | safe | structured | yes | no | `whoami` | `current user` | — |

## `text_inspection`

**Label:** Text inspection

**Description:** Inspect, filter, and transform file text content.

| Command | Category | Platforms | Risk | Maturity | Direct support | Network | Examples | Natural-language aliases | Notes |
|---|---|---|---|---|---|---|---|---|---|
| `cat` | inspection | all | safe | structured | yes | no | `cat README.md` | `show file contents`, `print file` | — |
| `grep` | search | all | safe | structured | yes | no | `grep -n TODO src/main.py` | `search text`, `find matching lines` | — |
| `head` | inspection | all | safe | structured | yes | no | `head -n 20 README.md` | `first lines` | — |
| `sort` | inspection | all | safe | structured | yes | no | `sort -u names.txt` | `sort lines` | — |
| `tail` | inspection | all | safe | structured | yes | no | `tail -n 50 app.log` | `last lines` | — |
| `uniq` | inspection | all | safe | structured | yes | no | `uniq -c names.txt` | `dedupe lines`, `unique lines` | — |
| `wc` | inspection | all | safe | structured | yes | no | `wc -l README.md` | `count lines`, `count words` | — |
