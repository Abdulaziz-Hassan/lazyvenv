import asyncio
from pathlib import Path

import pytest
from textual.widgets import DataTable, Label, ListView

from lazyvenv.app import LazyVenvApp
from lazyvenv.create import Interpreter
from lazyvenv.packages import Package
from lazyvenv.screens import CreateVenvScreen, PackageScreen
from lazyvenv.venvs import Venv

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


async def test_create_dialog_creates_venv(monkeypatch):
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

        app.post_message(DataTable.RowHighlighted(table, -1, None))
        app.post_message(DataTable.RowSelected(table, -1, None))
        await pilot.pause()

        assert str(app.query_one("#package-info", Label).render()) == ""
        assert len(app.screen_stack) == 1  # no detail screen opened
