from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.widgets import DataTable, ListView


class VenvList(ListView):
    """The left panel listing venvs — adds j/k navigation."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("a", "app.toggle_activation", "(De)activate"),
        Binding("c", "app.create_venv", "Create"),
        Binding("d", "app.delete_venv", "Delete"),
        Binding("r", "app.reload_venvs", "Refresh"),
    ]


class PackagesTable(DataTable):
    """The packages table — adds j/k navigation."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


class ScrollView(VerticalScroll):
    """A scrollable container with j/k scrolling (used by detail screens)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]
