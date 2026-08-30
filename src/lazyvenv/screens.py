"""Screens for lazyvenv: the package detail view and the modal dialogs."""

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select

from lazyvenv.create import Interpreter
from lazyvenv.packages import Package
from lazyvenv.venvs import Venv
from lazyvenv.widgets import ScrollView


class PackageScreen(Screen[None]):
    """Full-screen detail view for a single package."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "pop_screen", "Back"),
    ]

    def __init__(self, package: Package) -> None:
        super().__init__()
        self.package = package

    def compose(self) -> ComposeResult:
        """Show the complete metadata, including every dependency."""
        yield Header()
        with ScrollView():
            yield Label(self._full_details(), id="package-full")
        yield Footer()

    def on_mount(self) -> None:
        """Put the package name in the header's title."""
        self.title = f"lazyvenv — {self.package.name}"

    def action_pop_screen(self) -> None:
        """Return to the main screen."""
        self.app.pop_screen()

    def _full_details(self) -> str:
        """Render the full metadata text (Rich markup allowed)."""
        package = self.package
        lines = [
            f"[bold]{package.name}[/bold] {package.version}",
            f"[dim]{package.origin} · {package.installer or 'unknown installer'}[/dim]",
            "",
            package.summary,
            "",
            f"License:   {package.license or '-'}",
            f"Author:    {package.author or '-'}",
            f"Homepage:  {package.home_page or '-'}",
        ]
        if package.source_url:
            lines.append(f"Source:    {package.source_url}")
        lines.append("")
        lines.append(f"Requires ({len(package.requires)}):")
        if package.requires:
            lines.extend(f"  {requirement}" for requirement in package.requires)
        else:
            lines.append("  -")
        return "\n".join(lines)


class CreateVenvScreen(ModalScreen[tuple[str, Path] | None]):
    """Modal dialog to create a new venv with a chosen interpreter."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    CSS = """
    CreateVenvScreen {
        align: center middle;
    }

    #dialog {
        width: 64;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #dialog Label {
        margin-top: 1;
    }
    """

    def __init__(self, interpreters: list[Interpreter]) -> None:
        super().__init__()
        self.interpreters = interpreters

    def compose(self) -> ComposeResult:
        """Render the creation form."""
        with Vertical(id="dialog"):
            yield Label("[bold]Create virtual environment[/bold]")
            yield Label("Name")
            yield Input(value=".venv", id="name")
            yield Label("Interpreter")
            yield Select(
                [(i.label, str(i.path)) for i in self.interpreters],
                value=str(self.interpreters[0].path),
                id="python",
            )
            with Horizontal(id="buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Validate the form and dismiss with the user's choices."""
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        name = self.query_one("#name", Input).value.strip()
        python = self.query_one("#python", Select).value
        if not name:
            self.notify("Give the venv a name", severity="warning")
            return
        if (Path.cwd() / name).exists():
            self.notify(
                f"'{name}' already exists - pick another name", severity="warning"
            )
            return
        if python is Select.NULL:
            self.notify("Pick an interpreter", severity="warning")
            return
        self.dismiss((name, Path(str(python))))

    def action_cancel(self) -> None:
        """Close the dialog without creating anything."""
        self.dismiss(None)


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal dialog asking the user to confirm deletion of a venv."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }

    #delete-dialog {
        width: 64;
        height: auto;
        border: solid $error;
        background: $surface;
        padding: 1 2;
    }

    #delete-dialog .venv-path {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, venv: Venv) -> None:
        super().__init__()
        self.venv = venv

    def compose(self) -> ComposeResult:
        """Ask for confirmation, showing exactly what will be deleted."""
        with Vertical(id="delete-dialog"):
            yield Label(f"[bold]Delete '{self.venv.name}'?[/bold]")
            yield Label(self.venv.display_path, classes="venv-path")
            yield Label("[dim]This cannot be undone.[/dim]")
            with Horizontal(id="buttons"):
                yield Button("Delete", variant="error", id="delete")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Focus Cancel: confirming a deletion should be a deliberate move."""
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with True only when the Delete button was pressed."""
        self.dismiss(event.button.id == "delete")

    def action_cancel(self) -> None:
        """Close the dialog without deleting."""
        self.dismiss(False)
