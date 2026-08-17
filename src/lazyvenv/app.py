"""The lazyvenv Textual application."""

import asyncio
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView

from lazyvenv.create import UvCommandError, create_venv, list_interpreters
from lazyvenv.packages import Package, PackageInspectionError, list_packages
from lazyvenv.screens import CreateVenvScreen, PackageScreen
from lazyvenv.venvs import Venv, find_venvs


class LazyVenvApp(App):
    """A lazygit-style TUI for Python virtual environments."""

    TITLE = "lazyvenv"

    CSS = """
    #venvs {
        width: 36;
        border: solid $primary;
    }

    #details, #package-info {
        height: auto;
        max-height: 13;
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
        Binding("c", "create_venv", "Create"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.venvs: list[Venv] = []
        self.packages: dict[str, Package] = {}

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
                package_info = Label("", id="package-info")
                package_info.border_title = "Package Info"
                yield package_info
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
        info = self.query_one("#package-info", Label)
        table.loading = True
        info.update("")
        self.packages = {}
        try:
            packages = await asyncio.to_thread(list_packages, venv)
        except PackageInspectionError as error:
            table.clear()
            self.notify(f"Could not read packages: {error}", severity="error")
            return
        finally:
            table.loading = False
        self.packages = {package.name: package for package in packages}
        table.clear()
        for package in packages:
            table.add_row(package.name, package.version, key=package.name)
        if packages:
            info.update(self._describe_package(packages[0]))
        else:
            info.update("[dim]No packages installed in this venv.[/dim]")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Show metadata for the package under the table cursor."""
        if event.row_key is None:  # table is empty
            self.query_one("#package-info", Label).update("")
            return
        package = self.packages.get(event.row_key.value)
        if package is not None:
            self.query_one("#package-info", Label).update(
                self._describe_package(package)
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the full detail screen for the selected package."""
        if event.row_key is None:  # table is empty
            return
        package = self.packages.get(event.row_key.value)
        if package is not None:
            self.push_screen(PackageScreen(package))

    def action_create_venv(self) -> None:
        """Open the create-venv dialog."""
        self._open_create_dialog()

    @work
    async def _open_create_dialog(self) -> None:
        """Fetch interpreters in the background, then open the dialog."""
        try:
            interpreters = await asyncio.to_thread(list_interpreters)
        except UvCommandError as error:
            self.notify(f"Could not list interpreters: {error}", severity="error")
            return
        if not interpreters:
            self.notify(
                "No interpreters found — install one with `uv python install`",
                severity="warning",
            )
            return
        self.push_screen(CreateVenvScreen(interpreters), self._on_create_dismissed)

    def _on_create_dismissed(self, result: tuple[str, Path] | None) -> None:
        """Kick off creation when the dialog was submitted."""
        if result is not None:
            name, python_path = result
            self._create_venv(name, python_path)

    @work
    async def _create_venv(self, name: str, python_path: Path) -> None:
        """Run `uv venv` in the background, then refresh the venv list."""
        try:
            await asyncio.to_thread(create_venv, name, python_path, Path.cwd())
        except UvCommandError as error:
            self.notify(f"Could not create venv: {error}", severity="error")
            return
        self.notify(f"Created virtual environment '{name}'")
        self.load_venvs()

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

    @staticmethod
    def _describe_package(package: Package) -> str:
        """Render the package info pane text."""
        license_ = package.license.splitlines()[0] if package.license else "-"
        lines = [
            (
                f"[bold]{package.name}[/bold] {package.version}  "
                f"[dim]{package.origin} · {package.installer or 'unknown installer'}[/dim]"
            ),
            package.summary,
            "",
            f"License:   {license_}",
            f"Author:    {package.author or '-'}",
            f"Homepage:  {package.home_page or '-'}",
        ]
        if package.source_url:
            lines.append(f"Source:    [dim]{package.source_url}[/dim]")
        lines.extend(["", "[dim]⏎ full details[/dim]"])
        return "\n".join(lines)
