"""lazyvenv - a simple TUI for managing Python virtual environments."""

from lazyvenv.app import LazyVenvApp


def main() -> None:
    LazyVenvApp().run()
