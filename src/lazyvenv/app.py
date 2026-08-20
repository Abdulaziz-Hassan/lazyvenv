"""The lazyvenv Textual application."""

import asyncio
import os
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ListItem

from lazyvenv.activation import DEACTIVATE_COMMAND, activation_command
from lazyvenv.create import UvCommandError, create_venv, list_interpreters
from lazyvenv.packages import Package, PackageInspectionError, list_packages
from lazyvenv.screens import CreateVenvScreen, PackageScreen
from lazyvenv.venvs import Venv, find_venvs
from lazyvenv.widgets import PackagesTable, VenvList

NOTIFY_TIMEOUT = 2  # seconds


class LazyVenvApp(App):
    """A simple TUI for Python virtual environments."""

    TITLE = "lazyvenv"

    CSS = """
    #venvs {
        width: 36;
        border: solid $primary;
    }

    #venvs ListItem {
        padding: 1 2;
    }

    #details, #package-info {
        width: 1fr;
        height: 1fr;
        min-height: 7;
        max-height: 13;
        border: solid $secondary;
        padding: 1 2;
        overflow-y: auto;
    }

    #packages {
        height: 2fr;
        min-height: 7;
        border: solid $secondary;
    }

    #venvs:focus, #packages:focus {
        border: solid $accent;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("h", "focus_venvs", "Venvs panel", show=False),
        Binding("l", "focus_packages", "Packages panel", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.venvs: list[Venv] = []
        self.packages: dict[str, Package] = {}
        self.pending_command: str | None = None

    def _flash_toast(self, message: str) -> None:
        """Show a brief confirmation toast (default toasts linger 5s)."""
        self.notify(message, timeout=NOTIFY_TIMEOUT)

    def compose(self) -> ComposeResult:
        """Build the widget tree (called once when the app starts)."""
        yield Header()
        with Horizontal(id="main"):
            venv_list = VenvList(id="venvs")
            venv_list.border_title = "Venvs"
            yield venv_list
            with Vertical():
                details = Label("", id="details")
                details.border_title = "Details"
                yield details
                packages = PackagesTable(
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
        self.query_one("#packages", PackagesTable).add_columns("Name", "Version")
        self.load_venvs()
        self.query_one("#venvs", VenvList).focus()

    def load_venvs(self) -> None:
        """(Re)scan the current directory, rebuild the list, and keep selection."""
        self.venvs = find_venvs()
        venv_list = self.query_one("#venvs", VenvList)
        previous_index = venv_list.index
        venv_list.clear()
        venv_list.border_title = f"Venvs ({len(self.venvs)})"
        for venv in self.venvs:
            venv_list.append(ListItem(Label(self._label_for(venv))))
        if self.venvs:
            venv_list.index = min(previous_index or 0, len(self.venvs) - 1)
        else:
            self.query_one("#details", Label).update(
                "No virtual environments found in the current directory."
            )

    def _label_for(self, venv: Venv) -> str:
        """The list item text: status marker + name + version."""
        if venv.is_active:
            marker = (
                "[yellow]◆[/yellow] "
                if self.pending_command == DEACTIVATE_COMMAND
                else "[green]●[/green] "
            )
        elif self.pending_command == activation_command(venv):
            marker = "[yellow]◆[/yellow] "
        else:
            marker = ""
        return f"{marker}{venv.name}  [dim]{venv.python_version}[/dim]"

    def _refresh_markers(self) -> None:
        """Update list labels in place after the pending marker changes."""
        venv_list = self.query_one("#venvs", VenvList)
        for item, venv in zip(venv_list.children, self.venvs, strict=True):
            item.query_one(Label).update(self._label_for(venv))

    def on_list_view_highlighted(self, event: VenvList.Highlighted) -> None:
        """Update the right-hand panes when the cursor moves in the list."""
        if event.item is None:
            return
        venv = self.venvs[event.list_view.index]
        self.query_one("#details", Label).update(self._describe(venv))
        self.load_packages(venv)

    @work(exclusive=True)
    async def load_packages(self, venv: Venv) -> None:
        """Fetch the venv's packages in the background and fill the table."""
        table = self.query_one("#packages", PackagesTable)
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
        table.border_title = f"Packages ({len(packages)})"
        table.clear()
        for package in packages:
            table.add_row(package.name, package.version, key=package.name)
        if packages:
            info.update(self._describe_package(packages[0]))
        else:
            table.add_row(Text("(no pacakges installed)", style="dim italic"), "")
            info.update("[dim]No packages installed in this venv.[/dim]")

    def on_data_table_row_highlighted(
        self, event: PackagesTable.RowHighlighted
    ) -> None:
        """Show metadata for the package under the table cursor."""
        if event.row_key is None:  # table is empty
            self.query_one("#package-info", Label).update("")
            return
        package = self.packages.get(event.row_key.value)
        if package is not None:
            self.query_one("#package-info", Label).update(
                self._describe_package(package)
            )

    def on_data_table_row_selected(self, event: PackagesTable.RowSelected) -> None:
        """Open the full detail screen for the selected package."""
        if event.row_key is None:  # table is empty
            return
        package = self.packages.get(event.row_key.value)
        if package is not None:
            self.push_screen(PackageScreen(package))

    def action_toggle_activation(self) -> None:
        """Mark the highlighted venv for (de)activation on exit."""
        if not os.environ.get("LAZYVENV_SHELL_CMD_FILE"):
            self.notify(
                "Shell integration not installed — add this to your shell config:\n"
                'eval "$(lazyvenv init zsh)"',
                severity="warning",
            )
            return
        venv_list = self.query_one("#venvs", VenvList)
        if venv_list.index is None:
            return
        venv = self.venvs[venv_list.index]
        if venv.is_active:
            if self.pending_command == DEACTIVATE_COMMAND:
                self.pending_command = None
                self._flash_toast("Deactivation cancelled")
            else:
                self.pending_command = DEACTIVATE_COMMAND
                self._flash_toast(f"'{venv.name}' will deactivate on exit")
        else:
            command = activation_command(venv)
            if self.pending_command == command:
                self.pending_command = None
                self._flash_toast("Activation cancelled")
            else:
                self.pending_command = command
                self._flash_toast(f"'{venv.name}' will activate on exit")
        self._refresh_markers()

    def action_focus_venvs(self) -> None:
        """Focus the venv list (vim-style move to the left panel)."""
        self.query_one("#venvs", VenvList).focus()

    def action_focus_packages(self) -> None:
        """Focus the packages table (vim-style move to the right panel)."""
        self.query_one("#packages", PackagesTable).focus()

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
        self._flash_toast(f"Created virtual environment '{name}'")
        self.load_venvs()

    def action_reload_venvs(self) -> None:
        """Reload the venv list and show a confirmation toast."""
        self.load_venvs()
        self._flash_toast("Venv list refreshed")

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
