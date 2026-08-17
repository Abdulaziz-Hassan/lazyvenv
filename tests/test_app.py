import asyncio
from pathlib import Path

import pytest
from textual.widgets import DataTable, Label, ListView

from lazyvenv.app import LazyVenvApp
from lazyvenv.packages import Package
from lazyvenv.venvs import Venv

FAKE_VENVS = [
    Venv(Path("/fake/.venv"), "3.13.6", Path("/usr/bin"), False, True),
    Venv(Path("/fake/env"), "3.12.0", Path("/usr/bin"), False, False),
]

FAKE_PACKAGES = [
    Package("requests", "2.32.3", "Python HTTP for Humans."),
    Package("rich", "13.9.4", "Render rich text, tables, and more."),
]


@pytest.fixture(autouse=True)
def fake_data(monkeypatch):
    """Point the app at fake venvs/packages."""
    monkeypatch.setattr("lazyvenv.app.find_venvs", lambda directory=None: FAKE_VENVS)
    monkeypatch.setattr(
        "lazyvenv.app.list_packages", lambda venv, timeout=10: FAKE_PACKAGES
    )


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
        for _ in range(200):  # wait up to ~2s for the background worker
            await asyncio.sleep(0.01)
            if table.row_count == len(FAKE_PACKAGES):
                break
        assert table.row_count == len(FAKE_PACKAGES)
