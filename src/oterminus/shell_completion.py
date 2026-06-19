from __future__ import annotations

import shlex

from oterminus.config_settings import SUPPORTED_MUTABLE_CONFIG_KEYS, SUPPORTED_RESET_CONFIG_KEYS

SUPPORTED_SHELLS: tuple[str, ...] = ("zsh", "bash", "fish")
TOP_LEVEL_COMMANDS: tuple[str, ...] = ("doctor", "version", "completion", "config")
COMPLETION_SHELLS: tuple[str, ...] = SUPPORTED_SHELLS
CONFIG_COMMANDS: tuple[str, ...] = (
    "path",
    "show",
    "init",
    "validate",
    "edit",
    "get",
    "set",
    "reset",
)
CONFIG_INIT_OPTIONS: tuple[str, ...] = ("--defaults", "--force")
CONFIG_RESET_OPTIONS: tuple[str, ...] = ("--all-safe",)
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
    config_commands = _quoted_words(CONFIG_COMMANDS)
    config_init_options = _quoted_words(CONFIG_INIT_OPTIONS)
    config_keys = _quoted_words(SUPPORTED_MUTABLE_CONFIG_KEYS)
    config_reset_choices = _quoted_words((*SUPPORTED_RESET_CONFIG_KEYS, *CONFIG_RESET_OPTIONS))
    program = shlex.quote(program_name)
    return f"""#compdef {program}

_{program_name}() {{
  local state
  local -a commands
  local -a shells
  local -a config_commands
  local -a config_init_options
  local -a config_keys
  local -a config_reset_choices
  commands=({commands})
  shells=({shells})
  config_commands=({config_commands})
  config_init_options=({config_init_options})
  config_keys=({config_keys})
  config_reset_choices=({config_reset_choices})

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
      elif [[ $words[2] == config ]]; then
        _describe -t config-commands 'config command' config_commands
      fi
      ;;
    request)
      if [[ $words[2] == config && $words[3] == init ]]; then
        _describe -t config-init-options 'config init option' config_init_options
      elif [[ $words[2] == config && ( $words[3] == get || $words[3] == set ) && $CURRENT -eq 4 ]]; then
        _describe -t config-keys 'config key' config_keys
      elif [[ $words[2] == config && $words[3] == reset && $CURRENT -eq 4 ]]; then
        _describe -t config-reset-choices 'config reset target' config_reset_choices
      fi
      ;;
  esac
}}

_{program_name} "$@"
"""


def _render_bash(program_name: str) -> str:
    commands = _words(TOP_LEVEL_COMMANDS)
    shells = _words(COMPLETION_SHELLS)
    config_commands = _words(CONFIG_COMMANDS)
    config_init_options = _words(CONFIG_INIT_OPTIONS)
    config_keys = _words(SUPPORTED_MUTABLE_CONFIG_KEYS)
    config_reset_choices = _words((*SUPPORTED_RESET_CONFIG_KEYS, *CONFIG_RESET_OPTIONS))
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

  if [[ $prev == "config" ]]; then
    COMPREPLY=( $(compgen -W "{config_commands}" -- "$cur") )
    return 0
  fi

  if [[ ${{COMP_WORDS[1]}} == "config" && ${{COMP_WORDS[2]}} == "init" ]]; then
    COMPREPLY=( $(compgen -W "{config_init_options}" -- "$cur") )
    return 0
  fi

  if [[ ${{COMP_WORDS[1]}} == "config" && ( ${{COMP_WORDS[2]}} == "get" || ${{COMP_WORDS[2]}} == "set" ) && ${{COMP_CWORD}} -eq 3 ]]; then
    COMPREPLY=( $(compgen -W "{config_keys}" -- "$cur") )
    return 0
  fi

  if [[ ${{COMP_WORDS[1]}} == "config" && ${{COMP_WORDS[2]}} == "reset" && ${{COMP_CWORD}} -eq 3 ]]; then
    COMPREPLY=( $(compgen -W "{config_reset_choices}" -- "$cur") )
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
    config_words = " ".join(CONFIG_COMMANDS)
    config_key_words = " ".join(SUPPORTED_MUTABLE_CONFIG_KEYS)
    config_reset_key_words = " ".join(SUPPORTED_RESET_CONFIG_KEYS)
    return f"""# fish completion for {program_name}

complete -c {program_name} -f -l dry-run -d 'Plan and validate without executing'
complete -c {program_name} -f -l explain -d 'Explain the selected command without executing'
complete -c {program_name} -f -l version -d 'Print the installed OTerminus version'
complete -c {program_name} -f -l verbose -d 'Enable debug logging'
complete -c {program_name} -f -l help -d 'Show help'

{command_words}
complete -c {program_name} -n '__fish_seen_subcommand_from completion' -f -a "{shell_words}" -d 'Shell completion script'
complete -c {program_name} -n '__fish_seen_subcommand_from config' -f -a "{config_words}" -d 'Config command'
complete -c {program_name} -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from init' -f -l defaults -d 'Create safe defaults'
complete -c {program_name} -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from init' -f -l force -d 'Replace an existing valid config'
complete -c {program_name} -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from get' -f -a "{config_key_words}" -d 'Config key'
complete -c {program_name} -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set' -f -a "{config_key_words}" -d 'Config key'
complete -c {program_name} -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from reset' -f -a "{config_reset_key_words}" -d 'Config key'
complete -c {program_name} -n '__fish_seen_subcommand_from config; and __fish_seen_subcommand_from reset' -f -l all-safe -d 'Reset all safe config keys'
"""


def _fish_description(command: str) -> str:
    if command == "doctor":
        return "Run diagnostics"
    if command == "version":
        return "Print the installed OTerminus version"
    if command == "completion":
        return "Print a shell completion script"
    if command == "config":
        return "Manage configuration"
    return command
