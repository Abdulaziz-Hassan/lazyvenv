import asyncio
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Label, ListView

from lazyvenv.activation import activation_command
from lazyvenv.app import LazyVenvApp
from lazyvenv.create import Interpreter
from lazyvenv.packages import Package, PackageInspectionError
from lazyvenv.screens import ConfirmDeleteScreen, CreateVenvScreen, PackageScreen
from lazyvenv.venvs import Venv
from lazyvenv.widgets import FilterInput, PackagesTable, VenvList

FAKE_VENVS = [
    Venv(Path("/fake/.venv"), "3.13.6", Path("/usr/bin"), False, True),
    Venv(Path("/fake/env"), "3.12.0", Path("/usr/bin"), False, False),
]

FAKE_PACKAGES = [
    Package(
        "requests",
        "2.32.3",
        "Python HTTP for Humans.",
        "Apache-2.0",
        "Kenneth Reitz",
        "https://requests.readthedocs.io",
        ("certifi", "idna", "urllib3", "charset-normalizer"),
        "uv",
        "wheel",
        "https://files.pythonhosted.org/x/requests-2.32.3-py3-none-any.whl",
    ),
    Package(
        "rich",
        "13.9.4",
        "Render rich text, tables, and more.",
        "MIT",
        "Will McGugan",
        "https://github.com/Textualize/rich",
        ("pygments",),
        "uv",
        "wheel",
        "https://files.pythonhosted.org/x/rich-13.9.4-py3-none-any.whl",
    ),
]

FAKE_INTERPRETERS = [Interpreter("3.13.6", "cpython", Path("/fake/python3.13"))]


@pytest.fixture(autouse=True)
def fake_data(monkeypatch):
    """Point the app at fake venvs/packages."""
    monkeypatch.setattr("lazyvenv.app.find_venvs", lambda directory=None: FAKE_VENVS)
    monkeypatch.setattr(
        "lazyvenv.app.list_packages", lambda venv, timeout=10: FAKE_PACKAGES
    )


async def wait_for(condition):
    """Poll *condition* every 10ms, up to ~2s (for background workers)."""
    for _ in range(200):
        await asyncio.sleep(0.01)
        if condition():
            return
    raise AssertionError("condition was not met within 2s")


async def test_venvs_are_listed():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.query_one("#venvs", ListView).children) == 2


async def test_highlight_updates_details():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()

        venv_list = app.query_one("#venvs", ListView)
        details = app.query_one("#details", Label)
        assert venv_list.index is not None
        assert app.venvs[venv_list.index].name in str(details.render())


async def test_packages_fill_the_table():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        table = app.query_one("#packages", DataTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
        assert table.row_count == len(FAKE_PACKAGES)


async def test_package_row_updates_info_pane():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        table = app.query_one("#packages", DataTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
        table.focus()
        await pilot.press("down")
        await pilot.pause()

        assert table.cursor_row is not None
        info = app.query_one("#package-info", Label)
        assert FAKE_PACKAGES[table.cursor_row].name in str(info.render())


async def test_enter_opens_package_screen():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        table = app.query_one("#packages", DataTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
        table.focus()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PackageScreen)
        content = str(app.screen.query_one("#package-full", Label).render())
        assert "requests" in content
        assert "certifi" in content  # full dependency list, not truncated

        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1  # back to the main screen


async def test_create_dialog_creates_venv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    created = []
    monkeypatch.setattr("lazyvenv.app.list_interpreters", lambda: FAKE_INTERPRETERS)
    monkeypatch.setattr(
        "lazyvenv.app.create_venv",
        lambda name, python_path, directory: created.append((name, python_path)),
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await wait_for(lambda: isinstance(app.screen, CreateVenvScreen))

        await pilot.click("#create")
        await wait_for(lambda: len(created) == 1)
        assert created == [(".venv", Path("/fake/python3.13"))]
        assert len(app.screen_stack) == 1  # dialog closed after submit


async def test_create_dialog_rejects_existing_name(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".venv").mkdir()  # a directory with the default name exists
    created = []
    monkeypatch.setattr("lazyvenv.app.list_interpreters", lambda: FAKE_INTERPRETERS)
    monkeypatch.setattr(
        "lazyvenv.app.create_venv",
        lambda name, python_path, directory: created.append((name, python_path)),
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await wait_for(lambda: isinstance(app.screen, CreateVenvScreen))

        await pilot.click("#create")
        await pilot.pause()
        await asyncio.sleep(0.1)
        assert created == []
        assert isinstance(app.screen, CreateVenvScreen)  # dialog stays open


async def test_create_dialog_cancel_creates_nothing(monkeypatch):
    created = []
    monkeypatch.setattr("lazyvenv.app.list_interpreters", lambda: FAKE_INTERPRETERS)
    monkeypatch.setattr(
        "lazyvenv.app.create_venv",
        lambda name, python_path, directory: created.append((name, python_path)),
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await wait_for(lambda: isinstance(app.screen, CreateVenvScreen))

        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert created == []


async def test_empty_table_events_do_not_crash():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        table = app.query_one("#packages", DataTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))

        app.post_message(
            DataTable.RowHighlighted(table, -1, None)  # type: ignore[arg-type]
        )
        app.post_message(
            DataTable.RowSelected(table, -1, None)  # type: ignore[arg-type]
        )
        await pilot.pause()

        assert str(app.query_one("#package-info", Label).render()) == ""
        assert len(app.screen_stack) == 1  # no detail screen opened


async def highlight_index(pilot: Pilot[None], venv_list: ListView, target: int) -> None:
    """Move the venv list cursor to *target*, regardless of start state."""
    await pilot.press("down")
    await pilot.pause()
    while (index := venv_list.index) is not None and index != target:
        await pilot.press("up" if index > target else "down")
        await pilot.pause()


async def test_toggle_activation_marks_pending(monkeypatch):
    monkeypatch.setenv("LAZYVENV_SHELL_CMD_FILE", "/tmp/fake-cmd-file")
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", ListView)
        await highlight_index(pilot, venv_list, 0)

        await pilot.press("a")
        await pilot.pause()
        assert app.pending_command == "source '/fake/.venv/bin/activate'"

        await pilot.press("a")  # toggles back off
        await pilot.pause()
        assert app.pending_command is None


async def test_toggle_deactivation_on_the_active_venv(monkeypatch):
    monkeypatch.setenv("LAZYVENV_SHELL_CMD_FILE", "/tmp/fake-cmd-file")
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/.venv")  # FAKE_VENVS[0] is "active"
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", ListView)
        await highlight_index(pilot, venv_list, 0)

        await pilot.press("a")
        await pilot.pause()
        assert app.pending_command == "deactivate"


async def test_toggle_activation_without_hook_warns_and_marks_nothing(monkeypatch):
    monkeypatch.delenv("LAZYVENV_SHELL_CMD_FILE", raising=False)
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", ListView)
        await highlight_index(pilot, venv_list, 0)

        await pilot.press("a")
        await pilot.pause()
        assert app.pending_command is None


async def test_j_and_k_navigate_the_venv_list():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        venv_list.focus()
        await highlight_index(pilot, venv_list, 0)

        await pilot.press("j")
        await pilot.pause()
        assert venv_list.index == 1
        await pilot.press("k")
        await pilot.pause()
        assert venv_list.index == 0


async def test_h_and_l_switch_panels():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.focused, PackagesTable)

        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.focused, VenvList)


async def test_first_venv_is_preselected_on_launch():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        assert venv_list.index == 0
        assert ".venv" in str(app.query_one("#details", Label).render())
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))


async def test_no_venvs_resets_all_panels(monkeypatch):
    monkeypatch.setattr("lazyvenv.app.find_venvs", lambda directory=None: [])
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#venvs", VenvList).border_title == "Venvs (0)"
        assert "No virtual environments found" in str(
            app.query_one("#details", Label).render()
        )
        table = app.query_one("#packages", PackagesTable)
        assert table.border_title == "Packages (0)"
        assert table.row_count == 1  # the placeholder row


async def test_broken_venv_shows_a_message_instead_of_an_error(monkeypatch, tmp_path):
    broken_dir = tmp_path / "ghost"
    broken_dir.mkdir()  # dir exists, but no bin/python inside

    def explode(venv, timeout=10):
        raise AssertionError("list_packages must not run for a broken venv")

    monkeypatch.setattr(
        "lazyvenv.app.find_venvs",
        lambda directory=None: [
            Venv(broken_dir, "3.11.0", Path("/usr/bin"), False, False)
        ],
    )
    monkeypatch.setattr("lazyvenv.app.list_packages", explode)
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "[red]✗[/red]" in app._label_for(app.venvs[0])
        assert "Interpreter missing" in str(app.query_one("#details", Label).render())

        table = app.query_one("#packages", PackagesTable)
        assert table.border_title == "Packages"
        info = str(app.query_one("#package-info", Label).render())
        assert "no interpreter" in info


async def test_package_read_failure_shows_a_message_not_a_crash(monkeypatch):
    def fail(venv, timeout=10):
        raise PackageInspectionError("interpreter exploded")

    monkeypatch.setattr("lazyvenv.app.list_packages", fail)
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#packages", PackagesTable).border_title == "Packages"
        info = str(app.query_one("#package-info", Label).render())
        assert "interpreter exploded" in info


async def test_broken_venv_cannot_be_activated(monkeypatch, tmp_path):
    monkeypatch.setenv("LAZYVENV_SHELL_CMD_FILE", "/tmp/fake-cmd-file")
    broken_dir = tmp_path / "ghost"
    broken_dir.mkdir()  # dir exists, but no bin/python inside
    monkeypatch.setattr(
        "lazyvenv.app.find_venvs",
        lambda directory=None: [
            Venv(broken_dir, "3.11.0", Path("/usr/bin"), False, False)
        ],
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 0)

        await pilot.press("a")
        await pilot.pause()

        assert app.pending_command is None


async def test_empty_venv_shows_placeholder_in_both_panes(monkeypatch):
    monkeypatch.setattr("lazyvenv.app.list_packages", lambda venv, timeout=10: [])
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == 1)
        info = str(app.query_one("#package-info", Label).render())
        assert "No packages installed" in info


async def test_venv_actions_are_scoped_to_the_venv_panel(monkeypatch):
    monkeypatch.setenv("LAZYVENV_SHELL_CMD_FILE", "/tmp/fake-cmd-file")
    monkeypatch.setattr("lazyvenv.app.list_interpreters", lambda: FAKE_INTERPRETERS)
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#packages", PackagesTable).focus()
        await pilot.press("a")
        await pilot.press("c")
        await pilot.pause()
        await asyncio.sleep(0.1)

        assert app.pending_command is None
        assert len(app.screen_stack) == 1  # no create dialog opened


async def test_detail_screen_shadows_main_screen_bindings(monkeypatch):
    monkeypatch.setenv("LAZYVENV_SHELL_CMD_FILE", "/tmp/fake-cmd-file")
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PackageScreen)

        await pilot.press("a")
        await pilot.pause()
        assert app.pending_command is None

        await pilot.press("q")
        await pilot.pause()
        assert len(app.screen_stack) == 1  # popped the screen instead of quitting


async def test_pane_titles_show_counts():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#venvs", VenvList).border_title == "Venvs (2)"
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
        assert table.border_title == "Packages (2)"


async def test_details_hint_is_pinned_below_the_scrollable_body():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        hint = app.query_one("#package-info-hint", Label)
        assert str(hint.render()) == "⏎ full details"
        assert hint.parent is app.query_one("#package-info-pane")
        assert hint.parent is not app.query_one("#package-info")


async def open_filter(pilot: Pilot[None], app: LazyVenvApp) -> FilterInput:
    """Open the package filter from the packages table and return the input."""
    table = app.query_one("#packages", PackagesTable)
    await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
    table.focus()
    await pilot.press("/")
    await pilot.pause()
    filter_input: FilterInput = app.query_one("#package-filter", FilterInput)
    return filter_input


async def test_filter_narrows_the_packages_table():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = await open_filter(pilot, app)
        assert filter_input.display
        assert app.focused is filter_input

        await pilot.press(*"req")
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == 1)
        assert table.border_title == "Packages (1/2)"
        info = str(app.query_one("#package-info", Label).render())
        assert "requests" in info


async def test_filter_input_does_not_trigger_app_bindings():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = await open_filter(pilot, app)

        await pilot.press("h")  # would focus the venv panel if it leaked
        await pilot.press("q")  # would quit the app if it leaked
        await pilot.pause()

        assert filter_input.value == "hq"
        assert app.focused is filter_input


async def test_filter_escape_clears_and_closes():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = await open_filter(pilot, app)
        await pilot.press(*"req")
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == 1)

        await pilot.press("escape")
        await pilot.pause()
        assert not filter_input.display
        assert filter_input.value == ""
        assert table.row_count == len(FAKE_PACKAGES)
        assert app.focused is table


async def test_filter_with_no_matches_shows_placeholder():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await open_filter(pilot, app)
        await pilot.press(*"zzz")

        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == 1)  # the placeholder row
        assert table.border_title == "Packages (0/2)"
        info = str(app.query_one("#package-info", Label).render())
        assert "requests" not in info and "rich" not in info


async def test_switching_venvs_resets_the_filter():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = await open_filter(pilot, app)
        await pilot.press(*"req")
        table = app.query_one("#packages", PackagesTable)
        await wait_for(lambda: table.row_count == 1)

        app.query_one("#venvs", VenvList).focus()
        await pilot.press("down")  # move to the other venv
        await wait_for(lambda: table.row_count == len(FAKE_PACKAGES))
        assert not filter_input.display
        assert filter_input.value == ""
        assert table.border_title == "Packages (2)"


async def test_details_show_size_after_background_load(monkeypatch):
    monkeypatch.setattr("lazyvenv.app.directory_size", lambda path: 2 * 1024**2)
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        details = app.query_one("#details", Label)
        await wait_for(lambda: "2.0 MB" in str(details.render()))


async def test_markers_are_color_coded(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/.venv")
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "[green]●[/green]" in app._label_for(app.venvs[0])
        app.pending_command = activation_command(app.venvs[1])
        assert "[yellow]◆[/yellow]" in app._label_for(app.venvs[1])


def test_package_description_truncates_long_authors():
    package = Package(
        name="x",
        version="1.0",
        summary="",
        license="MIT",
        author="A" * 100,
        home_page="",
        requires=(),
        installer="",
        origin="registry",
        source_url="",
    )
    text = LazyVenvApp._describe_package(package)
    assert "A" * 100 not in text
    assert "A" * 57 in text


async def test_delete_venv_removes_it_from_the_list(monkeypatch):
    deleted = []
    monkeypatch.setattr("lazyvenv.app.delete_venv", lambda venv: deleted.append(venv))
    monkeypatch.setattr(
        "lazyvenv.app.find_venvs",
        lambda directory=None: [v for v in FAKE_VENVS if v not in deleted],
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 1)

        await pilot.press("d")
        await wait_for(lambda: isinstance(app.screen, ConfirmDeleteScreen))
        screen = app.screen
        assert isinstance(screen, ConfirmDeleteScreen)
        assert screen.venv == FAKE_VENVS[1]

        await pilot.click("#delete")
        await wait_for(lambda: len(deleted) == 1)
        await wait_for(lambda: len(venv_list.children) == 1)
        assert deleted == [FAKE_VENVS[1]]


async def test_delete_dialog_focuses_cancel_by_default(monkeypatch):
    deleted = []
    monkeypatch.setattr("lazyvenv.app.delete_venv", lambda venv: deleted.append(venv))
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 1)

        await pilot.press("d")
        await wait_for(lambda: isinstance(app.screen, ConfirmDeleteScreen))
        assert app.screen.focused is app.screen.query_one("#cancel", Button)

        await pilot.press("enter")  # hits Cancel, not Delete
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert deleted == []


async def test_focused_cancel_button_uses_subtle_style():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 1)

        await pilot.press("d")
        await wait_for(lambda: isinstance(app.screen, ConfirmDeleteScreen))
        await pilot.pause()

        cancel = app.screen.query_one("#cancel", Button)
        assert "focus" in cancel.pseudo_classes
        assert "reverse" not in str(cancel.styles.text_style)
        assert "underline" not in str(cancel.styles.text_style)


async def test_hover_does_not_change_button_edges():
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 1)

        await pilot.press("d")
        await wait_for(lambda: isinstance(app.screen, ConfirmDeleteScreen))
        cancel = app.screen.query_one("#cancel", Button)
        edge_before = cancel.styles.border_top

        await pilot.hover("#cancel")
        await pilot.pause()

        assert cancel.styles.border_top == edge_before


async def test_delete_dialog_cancel_deletes_nothing(monkeypatch):
    deleted = []
    monkeypatch.setattr("lazyvenv.app.delete_venv", lambda venv: deleted.append(venv))
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 1)

        await pilot.press("d")
        await wait_for(lambda: isinstance(app.screen, ConfirmDeleteScreen))
        await pilot.press("escape")
        await pilot.pause()

        assert len(app.screen_stack) == 1
        assert deleted == []


async def test_delete_refuses_the_active_venv(monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/.venv")
    deleted = []
    monkeypatch.setattr("lazyvenv.app.delete_venv", lambda venv: deleted.append(venv))
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 0)

        await pilot.press("d")
        await pilot.pause()
        await asyncio.sleep(0.1)

        assert len(app.screen_stack) == 1  # no dialog opened
        assert deleted == []


async def test_delete_clears_a_pending_activation_marker(monkeypatch):
    monkeypatch.setenv("LAZYVENV_SHELL_CMD_FILE", "/tmp/fake-cmd-file")
    monkeypatch.setattr("lazyvenv.app.delete_venv", lambda venv: None)
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", VenvList)
        await highlight_index(pilot, venv_list, 1)

        await pilot.press("a")  # mark 'env' for activation
        await pilot.pause()
        assert app.pending_command == "source '/fake/env/bin/activate'"

        await pilot.press("d")
        await wait_for(lambda: isinstance(app.screen, ConfirmDeleteScreen))
        await pilot.click("#delete")
        await wait_for(lambda: app.pending_command is None)
