from __future__ import annotations

import shlex

SUPPORTED_SHELLS: tuple[str, ...] = ("zsh", "bash", "fish")
TOP_LEVEL_COMMANDS: tuple[str, ...] = ("doctor", "version", "completion")
COMPLETION_SHELLS: tuple[str, ...] = SUPPORTED_SHELLS
TOP_LEVEL_FLAGS: tuple[str, ...] = (
    "--dry-run",
    "--explain",
    "--version",
    "--verbose",
    "--help",
)


def supported_shells() -> tuple[str, ...]:
    return SUPPORTED_SHELLS


def render_shell_completion(shell: str, program_name: str = "oterminus") -> str:
    normalized_shell = shell.strip().lower()
    if normalized_shell not in SUPPORTED_SHELLS:
        supported = ", ".join(SUPPORTED_SHELLS)
        raise ValueError(f"Unsupported shell '{shell}'. Supported shells: {supported}.")

    if normalized_shell == "zsh":
        return _render_zsh(program_name)
    if normalized_shell == "bash":
        return _render_bash(program_name)
    return _render_fish(program_name)


def _words(values: tuple[str, ...]) -> str:
    return " ".join(values)


def _quoted_words(values: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(value) for value in values)


def _render_zsh(program_name: str) -> str:
    commands = _quoted_words(TOP_LEVEL_COMMANDS)
    shells = _quoted_words(COMPLETION_SHELLS)
    program = shlex.quote(program_name)
    return f"""#compdef {program}

_{program_name}() {{
  local state
  local -a commands
  local -a shells
  commands=({commands})
  shells=({shells})

  _arguments -C \\
    '--dry-run[plan and validate without executing]' \\
    '--explain[explain the selected command without executing]' \\
    '--version[print the installed OTerminus version]' \\
    '--verbose[enable debug logging]' \\
    '--help[show help]' \\
    '1:command:->command' \\
    '2:shell:->shell' \\
    '*:request:->request'

  case "$state" in
    command)
      _describe -t commands 'oterminus command' commands
      ;;
    shell)
      if [[ $words[2] == completion ]]; then
        _describe -t shells 'shell' shells
      fi
      ;;
  esac
}}

_{program_name} "$@"
"""


def _render_bash(program_name: str) -> str:
    commands = _words(TOP_LEVEL_COMMANDS)
    shells = _words(COMPLETION_SHELLS)
    flags = _words(TOP_LEVEL_FLAGS)
    function_name = f"_{program_name}_completion"
    return f"""# bash completion for {program_name}

{function_name}() {{
  local cur prev
  COMPREPLY=()
  cur="${{COMP_WORDS[COMP_CWORD]}}"
  prev="${{COMP_WORDS[COMP_CWORD-1]}}"

  if [[ ${{COMP_CWORD}} -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "{flags} {commands}" -- "$cur") )
    return 0
  fi

  if [[ $prev == "completion" ]]; then
    COMPREPLY=( $(compgen -W "{shells}" -- "$cur") )
    return 0
  fi

  COMPREPLY=()
  return 0
}}

complete -F {function_name} {program_name}
"""


def _render_fish(program_name: str) -> str:
    command_words = "\n".join(
        f"complete -c {program_name} -n 'not __fish_seen_subcommand_from "
        f"{_words(TOP_LEVEL_COMMANDS)}' -f -a {command} "
        f"-d '{_fish_description(command)}'"
        for command in TOP_LEVEL_COMMANDS
    )
    shell_words = " ".join(COMPLETION_SHELLS)
    return f"""# fish completion for {program_name}

complete -c {program_name} -f -l dry-run -d 'Plan and validate without executing'
complete -c {program_name} -f -l explain -d 'Explain the selected command without executing'
complete -c {program_name} -f -l version -d 'Print the installed OTerminus version'
complete -c {program_name} -f -l verbose -d 'Enable debug logging'
complete -c {program_name} -f -l help -d 'Show help'

{command_words}
complete -c {program_name} -n '__fish_seen_subcommand_from completion' -f -a "{shell_words}" -d 'Shell completion script'
"""


def _fish_description(command: str) -> str:
    if command == "doctor":
        return "Run diagnostics"
    if command == "version":
        return "Print the installed OTerminus version"
    if command == "completion":
        return "Print a shell completion script"
    return command
