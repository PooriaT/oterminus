# Command Families Reference

This table summarizes curated command families, risk, and maturity. Maturity describes how a command family is allowed to participate in the two first-class proposal modes: structured or experimental.

| Command | Capability | Risk | Maturity |
|---|---|---|---|
| cd | filesystem_inspection | safe | direct_only |
| ls | filesystem_inspection | safe | structured |
| pwd | filesystem_inspection | safe | structured |
| find | filesystem_inspection | safe | structured |
| du | filesystem_inspection | safe | structured |
| stat | filesystem_inspection | safe | structured |
| file | filesystem_inspection | safe | structured |
| mkdir | filesystem_mutation | write | structured |
| cp | filesystem_mutation | write | structured |
| mv | filesystem_mutation | write | structured |
| chmod | filesystem_mutation | write | structured |
| touch | filesystem_mutation | write | experimental_only |
| chown | filesystem_mutation | dangerous | experimental_only |
| cat | text_inspection | safe | structured |
| head | text_inspection | safe | structured |
| tail | text_inspection | safe | structured |
| grep | text_inspection | safe | structured |
| wc | text_inspection | safe | structured |
| sort | text_inspection | safe | structured |
| uniq | text_inspection | safe | structured |
| ps | process_inspection | safe | structured |
| pgrep | process_inspection | safe | structured |
| lsof | process_inspection | safe | structured |
| clear | system_inspection | safe | structured |
| whoami | system_inspection | safe | structured |
| uname | system_inspection | safe | structured |
| which | system_inspection | safe | structured |
| env | system_inspection | safe | structured |
| df | system_inspection | safe | structured |
| open | macos_desktop | safe | structured |
| rm | destructive_operations | dangerous | experimental_only |
| sudo | destructive_operations | dangerous | blocked |

Notes:

- `structured` means the preferred path is available: `command_family + arguments` with deterministic Python rendering.
- `direct_only` means accepted as direct command input, without a full structured family schema path.
- `experimental_only` means constrained experimental fallback only; it is not a substitute for structured design when a safe schema is practical.
- `blocked` means tracked in registry but rejected by maturity policy.
- Experimental mode has stronger confirmation requirements and remains strictly validated.
