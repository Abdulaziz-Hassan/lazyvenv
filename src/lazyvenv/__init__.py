"""lazyvenv - a simple TUI for managing Python virtual environments."""

from lazyvenv.venvs import find_venvs


def main() -> None:
    venvs = find_venvs()
    if not venvs:
        print("No virtual environments found in the current directory.")
        return
    for venv in venvs:
        marker = "*" if venv.is_active else " "
        print(f"{marker} {venv.name} (Python {venv.python_version})")
