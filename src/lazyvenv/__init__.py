"""lazyvenv - a TUI for managing Python virtual environments."""

import argparse
import os
import sys
from importlib.metadata import version
from pathlib import Path

from lazyvenv.activation import activation_command, init_script
from lazyvenv.venvs import find_venvs


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lazyvenv",
        description="A TUI for managing Python virtual environments.",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {version('lazyvenv')}",
    )
    subparsers = parser.add_subparsers(dest="command")

    activate = subparsers.add_parser(
        "activate", help="print the activate command (used by the shell hook)"
    )
    activate.add_argument("name", help="name of the venv to activate")

    init = subparsers.add_parser("init", help="print the shell wrapper function")
    init.add_argument("shell", nargs="?", default="zsh", choices=["zsh", "bash"])

    args = parser.parse_args()
    if args.command == "activate":
        _print_activation(args.name)
    elif args.command == "init":
        _print_init(args.shell)
    else:
        _run_tui()


def _print_activation(name: str) -> None:
    """Print the ``source`` command for the named venv."""
    for venv in find_venvs():
        if venv.name == name:
            print(activation_command(venv))
            return
    sys.exit(f"lazyvenv: no venv named '{name}' in {Path.cwd()}")


def _print_init(shell: str) -> None:
    """Print the shell wrapper function (zsh/bash)."""
    print(init_script(shell))


def _run_tui() -> None:
    """Launch the TUI, then apply any pending (de)activation."""
    from lazyvenv.app import LazyVenvApp  # deferred: importing textual is slow

    app = LazyVenvApp()
    app.run()
    cmd_file = os.environ.get("LAZYVENV_SHELL_CMD_FILE")
    if cmd_file and app.pending_command:
        Path(cmd_file).write_text(app.pending_command + "\n")
