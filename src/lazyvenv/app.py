"""The lazyvenv Textual application."""

import asyncio
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView

from lazyvenv.packages import PackageInspectionError, list_packages
from lazyvenv.venvs import Venv, find_venvs


class LazyVenvApp(App):
    """A simple TUI for Python virtual environments."""

    TITLE = "lazyvenv"

    CSS = """
    #venvs {
        width: 36;
        border: solid $primary;
    }

    #details {
        height: 11;
        border: solid $secondary;
        padding: 1 2;
    }

    #packages {
        border: solid $secondary;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reload_venvs", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.venvs: list[Venv] = []

    def compose(self) -> ComposeResult:
        """Build the widget tree (called once when the app starts)."""
        yield Header()
        with Horizontal(id="main"):
            venv_list = ListView(id="venvs")
            venv_list.border_title = "Venvs"
            yield venv_list
            with Vertical():
                details = Label("", id="details")
                details.border_title = "Details"
                yield details
                packages = DataTable(
                    id="packages", cursor_type="row", zebra_stripes=True
                )
                packages.border_title = "Packages"
                yield packages
        yield Footer()

    def on_mount(self) -> None:
        """Populate the venv list once the widget tree is ready."""
        self.query_one("#packages", DataTable).add_columns("Name", "Version")
        self.load_venvs()

    def load_venvs(self) -> None:
        """(Re)scan the current directory and rebuild the list."""
        self.venvs = find_venvs()
        venv_list = self.query_one("#venvs", ListView)
        venv_list.clear()
        for venv in self.venvs:
            marker = "● " if venv.is_active else ""
            label = Label(f"{marker}{venv.name}  [dim]{venv.python_version}[/dim]")
            venv_list.append(ListItem(label))
        if not self.venvs:
            self.query_one("#details", Label).update(
                "No virtual environments found in the current directory."
            )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update the right-hand panes when the cursor moves in the list."""
        if event.item is None:
            return
        venv = self.venvs[event.list_view.index]
        self.query_one("#details", Label).update(self._describe(venv))
        self.load_packages(venv)

    @work(exclusive=True)
    async def load_packages(self, venv: Venv) -> None:
        """Fetch the venv's packages in the background and fill the table."""
        table = self.query_one("#packages", DataTable)
        table.loading = True
        try:
            packages = await asyncio.to_thread(list_packages, venv)
        except PackageInspectionError as error:
            table.clear()
            self.notify(f"Could not read packages: {error}", severity="error")
            return
        finally:
            table.loading = False
        table.clear()
        table.add_rows((package.name, package.version) for package in packages)

    def action_reload_venvs(self) -> None:
        """Reload the venv list and show a confirmation toast."""
        self.load_venvs()
        self.notify("Venv list refreshed")

    @staticmethod
    def _describe(venv: Venv) -> str:
        """Render the details pane text for a venv."""
        creator = "uv" if venv.created_by_uv else "python -m venv"
        active = "yes" if venv.is_active else "no"
        return (
            f"[bold]{venv.name}[/bold]\n\n"
            f"Path:    {venv.path}\n"
            f"Python:  {venv.python_version}\n"
            f"Base:    {venv.home}\n"
            f"Created: {creator}\n"
            f"Active:  {active}"
        )
