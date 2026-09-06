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
from textual.widgets import Footer, Header, Input, Label, ListItem

from lazyvenv.activation import DEACTIVATE_COMMAND, activation_command
from lazyvenv.create import UvCommandError, create_venv, list_interpreters
from lazyvenv.packages import Package, PackageInspectionError, list_packages
from lazyvenv.screens import ConfirmDeleteScreen, CreateVenvScreen, PackageScreen
from lazyvenv.venvs import (
    Venv,
    collapse_home,
    delete_venv,
    directory_size,
    find_venvs,
    human_size,
)
from lazyvenv.widgets import FilterInput, PackagesTable, VenvList

NOTIFY_TIMEOUT = 2  # seconds


class LazyVenvApp(App[None]):
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

    #details {
        width: 1fr;
        height: 1fr;
        min-height: 7;
        max-height: 13;
        border: solid $secondary;
        padding: 1 2;
        overflow-y: auto;
    }

    #package-info-pane {
        width: 1fr;
        min-height: 7;
        max-height: 13;
        border: solid $secondary;
    }

    #package-info {
        height: 1fr;
        min-height: 4;
        padding: 1 2;
        overflow-y: auto;
    }

    #package-info-hint {
        height: 1;
        padding: 0 2;
        color: $text-muted;
        text-style: dim;
    }

    #packages {
        height: 2fr;
        min-height: 7;
        border: solid $secondary;
    }

    #package-filter {
        display: none;
        margin-bottom: 1;
    }

    #venvs:focus, #packages:focus {
        border: solid $accent;
    }

    /* shared dialog chrome (create + delete dialogs) */
    #buttons {
        height: auto;
        margin-top: 1;
    }

    #buttons Button {
        margin-right: 2;
    }

    #cancel:focus {
        text-style: bold;
        background: $boost;
    }

    #cancel:hover {
        background: $surface-lighten-2;
        border-top: tall $surface-lighten-1;
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

    def _set_package_info(self, text: str, hint: bool = True) -> None:
        """Fill the package info pane and show/hide its fixed details hint."""
        self.query_one("#package-info", Label).update(text)
        self.query_one("#package-info-hint", Label).visible = hint

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
                yield FilterInput(placeholder="Filter packages…", id="package-filter")
                packages = PackagesTable(
                    id="packages", cursor_type="row", zebra_stripes=True
                )
                packages.border_title = "Packages"
                yield packages
                with Vertical(id="package-info-pane") as info_pane:
                    info_pane.border_title = "Package Info"
                    yield Label("", id="package-info")
                    yield Label("⏎ full details", id="package-info-hint")
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
            self.packages = {}
            self._apply_filter("")

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
        if event.list_view.index is None:  # list is empty
            return
        venv = self.venvs[event.list_view.index]
        self.query_one("#details", Label).update(self._describe(venv))
        self.load_size(venv)
        self.load_packages(venv)

    @work(exclusive=True, group="sizes")
    async def load_size(self, venv: Venv) -> None:
        """Measure the venv's disk usage in the background, then show it."""
        size = await asyncio.to_thread(directory_size, venv.path)
        venv_list = self.query_one("#venvs", VenvList)
        if venv_list.index is not None and self.venvs[venv_list.index] == venv:
            self.query_one("#details", Label).update(self._describe(venv, size))

    @work(exclusive=True)
    async def load_packages(self, venv: Venv) -> None:
        """Fetch the venv's packages in the background and fill the table."""
        table = self.query_one("#packages", PackagesTable)
        table.loading = True
        self._set_package_info("", hint=False)
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
        filter_input = self.query_one("#package-filter", FilterInput)
        filter_input.value = ""
        filter_input.display = False
        self._apply_filter("")

    def _apply_filter(self, query: str) -> None:
        """Rebuild the packages table, keeping only rows matching *query*."""
        table = self.query_one("#packages", PackagesTable)
        matches = [
            package
            for package in self.packages.values()
            if query.lower() in package.name.lower()
        ]
        if query:
            table.border_title = f"Packages ({len(matches)}/{len(self.packages)})"
        else:
            table.border_title = f"Packages ({len(self.packages)})"
        table.clear()
        for package in matches:
            table.add_row(package.name, package.version, key=package.name)
        if matches:
            self._set_package_info(self._describe_package(matches[0]))
            return
        if self.packages:
            placeholder = f"(no packages match '{query}')"
            info = ""
        else:
            placeholder = "(no packages installed)"
            info = "[dim]No packages installed in this venv.[/dim]"
        table.add_row(Text(placeholder, style="dim italic"), "")
        self._set_package_info(info, hint=False)

    def on_data_table_row_highlighted(
        self, event: PackagesTable.RowHighlighted
    ) -> None:
        """Show metadata for the package under the table cursor."""
        if event.row_key is None:  # table is empty
            self._set_package_info("", hint=False)
            return
        package = self.packages.get(event.row_key.value or "")
        if package is not None:
            self._set_package_info(self._describe_package(package))

    def on_data_table_row_selected(self, event: PackagesTable.RowSelected) -> None:
        """Open the full detail screen for the selected package."""
        if event.row_key is None:  # table is empty
            return
        package = self.packages.get(event.row_key.value or "")
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

    def action_filter_packages(self) -> None:
        """Show and focus the package filter input."""
        filter_input = self.query_one("#package-filter", FilterInput)
        filter_input.display = True
        filter_input.focus()

    def action_clear_filter(self) -> None:
        """Clear the package filter, hide the input, refocus the table."""
        filter_input = self.query_one("#package-filter", FilterInput)
        filter_input.value = ""
        filter_input.display = False
        self._apply_filter("")
        self.query_one("#packages", PackagesTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the packages table as the query is typed."""
        if event.input.id == "package-filter":
            self._apply_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Keep the filter and return focus to the packages table."""
        if event.input.id == "package-filter":
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

    def action_delete_venv(self) -> None:
        """Ask for confirmation, then delete the highlighted venv."""
        venv_list = self.query_one("#venvs", VenvList)
        if venv_list.index is None:
            return
        venv = self.venvs[venv_list.index]
        if venv.is_active:
            self.notify(
                f"'{venv.name}' is active - deactivate it first",
                severity="warning",
            )
            return
        self.push_screen(
            ConfirmDeleteScreen(venv),
            lambda confirmed: self._on_delete_dismissed(venv, confirmed),
        )

    def _on_delete_dismissed(self, venv: Venv, confirmed: bool) -> None:
        """Kick off deletion when the dialog was confirmed."""
        if confirmed:
            self._delete_venv(venv)

    @work
    async def _delete_venv(self, venv: Venv) -> None:
        """Delete the venv directory in the background, then refresh the list."""
        try:
            await asyncio.to_thread(delete_venv, venv)
        except OSError as error:
            self.notify(f"Could not delete '{venv.name}': {error}", severity="error")
            return
        if self.pending_command == activation_command(venv):
            self.pending_command = None
        self._flash_toast(f"Deleted virtual environment '{venv.name}'")
        self.load_venvs()

    @staticmethod
    def _describe(venv: Venv, size: int | None = None) -> str:
        """Render the details pane text for a venv."""
        creator = "uv" if venv.created_by_uv else "python -m venv"
        active = "yes" if venv.is_active else "no"
        size_text = human_size(size) if size else "…"
        return (
            f"[bold]{venv.name}[/bold]\n\n"
            f"Path:    {venv.display_path}\n"
            f"Size:    {size_text}\n"
            f"Python:  {venv.python_version}\n"
            f"Base:    {collapse_home(venv.home)}\n"
            f"Created: {creator}\n"
            f"Active:  {active}"
        )

    @staticmethod
    def _describe_package(package: Package) -> str:
        """Render the package info pane text."""
        license_ = package.license.splitlines()[0] if package.license else "-"
        author = package.author
        if len(author) > 60:
            author = author[:57].rstrip() + "..."
        lines = [
            (
                f"[bold]{package.name}[/bold] {package.version}  "
                f"[dim]{package.origin} · {package.installer or 'unknown installer'}[/dim]"  # noqa: E501
            ),
            package.summary,
            "",
            f"License:   {license_}",
            f"Author:    {author or '-'}",
            f"Homepage:  {package.home_page or '-'}",
        ]
        if package.source_url:
            lines.append(f"Source:    [dim]{package.source_url}[/dim]")
        return "\n".join(lines)
