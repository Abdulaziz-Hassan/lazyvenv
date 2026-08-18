"""lazyvenv - a simple TUI for managing Python virtual environments."""

import os
import sys
from pathlib import Path

from lazyvenv.activation import activation_command, init_script
from lazyvenv.venvs import find_venvs


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["activate"]:
        _print_activation(args[1:])
    elif args[:1] == ["init"]:
        _print_init(args[1:])
    else:
        _run_tui()


def _print_activation(args: list[str]) -> None:
    """Print the ``source`` command for the named venv."""
    if not args:
        sys.exit("usage: lazyvenv activate <name>")
    name = args[0]
    for venv in find_venvs():
        if venv.name == name:
            print(activation_command(venv))
            return
    sys.exit(f"lazyvenv: no venv named '{name}' in {Path.cwd()}")


def _print_init(args: list[str]) -> None:
    """Print the shell wrapper function (zsh/bash)."""
    shell = args[0] if args else "zsh"
    try:
        print(init_script(shell))
    except ValueError as error:
        sys.exit(f"lazyvenv: {error}")


def _run_tui() -> None:
    """Launch the TUI, then apply any pending (de)activation."""
    from lazyvenv.app import LazyVenvApp  # deferred: importing textual is slow

    app = LazyVenvApp()
    app.run()
    cmd_file = os.environ.get("LAZYVENV_SHELL_CMD_FILE")
    if cmd_file and app.pending_command:
        Path(cmd_file).write_text(app.pending_command + "\n")
