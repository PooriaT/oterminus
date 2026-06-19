# Shell Completion

OTerminus supports two separate completion surfaces:

- **Shell-level completion** runs in your outer shell before OTerminus starts. It helps complete the
  `oterminus` command, top-level flags, top-level subcommands, config subcommands, config init
  options, safe config get/set keys, and completion shell names.
- **REPL Tab autocomplete** runs inside interactive OTerminus after you start `oterminus`. It helps
  complete REPL built-ins, supported command families, capability IDs, and local filesystem paths.

Shell-level completion is opt-in. OTerminus prints completion scripts for supported shells, but it
does not install them automatically and never edits `.zshrc`, `.bashrc`, `config.fish`, or other
shell startup files.

## Supported shells

OTerminus can generate completion scripts for:

- zsh
- bash
- fish

Generate a script with one of these commands:

```bash
oterminus completion zsh
oterminus completion bash
oterminus completion fish
```

Each command writes the generated script to stdout. Redirect it to a completion file or inspect it
first in your terminal.

## zsh

One safe manual setup is to place the generated completion file in a directory that you add to
`fpath`:

```bash
mkdir -p ~/.zsh/completions
oterminus completion zsh > ~/.zsh/completions/_oterminus
```

Then add the completion directory to your zsh configuration yourself, for example in `~/.zshrc`:

```bash
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit
compinit
```

Restart your shell, or start a new terminal session, after changing zsh completion configuration.
This is not the only valid zsh completion setup; use the layout that matches your shell
configuration.

To remove this setup, delete the generated completion file and remove the related `fpath` or
`compinit` lines if you added them only for OTerminus:

```bash
rm ~/.zsh/completions/_oterminus
```

## bash

One safe manual setup is to keep generated completion files under a user-owned directory:

```bash
mkdir -p ~/.bash_completion.d
oterminus completion bash > ~/.bash_completion.d/oterminus
```

You can source the file manually in the current shell:

```bash
source ~/.bash_completion.d/oterminus
```

Or add that `source` line to `~/.bashrc` yourself if that matches your environment. Bash completion
setup varies by operating system and distribution, so adapt the location and startup file to your
shell configuration.

To remove this setup, delete the generated completion file and remove the `source` line if you added
one:

```bash
rm ~/.bash_completion.d/oterminus
```

## fish

Fish normally loads completion files from `~/.config/fish/completions`:

```bash
mkdir -p ~/.config/fish/completions
oterminus completion fish > ~/.config/fish/completions/oterminus.fish
```

Restart fish, or start a new terminal session, after adding the completion file. OTerminus does not
modify `config.fish` automatically.

To remove this setup, delete the generated completion file:

```bash
rm ~/.config/fish/completions/oterminus.fish
```

## Safety notes

`oterminus completion <shell>` only prints a script. It does not call Ollama, start the REPL, install
files, source files, or modify shell startup files.

The generated static scripts include top-level `config`, the config subcommands `path`, `show`,
`get`, `set`, `init`, `validate`, and `edit`, and the `config init` options `--defaults` and
`--force` where the shell format can express that context. After `oterminus config get` and
`oterminus config set`, scripts complete only the safe supported keys: `model`, `command_profile`,
`auto_execute_safe`, `audit_enabled`, `audit_redact`, `history_enabled`, `history_redact`,
`explain_failures`, `color_mode`, `timeout_seconds`, and `max_output_chars`. Dangerous or advanced
fields such as `allow_dangerous`, `policy.allow_dangerous`, `allowed_roots`, schema fields, paths,
and list settings are not completed. Completion generation never runs OTerminus dynamically.

If completion does not appear after installation, verify that your shell is loading the generated
file from the location you chose. Shell completion setup is controlled by your shell configuration,
not by OTerminus.
