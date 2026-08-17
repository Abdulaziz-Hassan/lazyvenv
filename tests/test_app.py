from pathlib import Path

from textual.widgets import Label, ListView

from lazyvenv.app import LazyVenvApp
from lazyvenv.venvs import Venv


def fake_venv(name: str) -> Venv:
    """A Venv that exists only in memory."""
    return Venv(
        path=Path("/fake") / name,
        python_version="3.13.6",
        home=Path("/usr/bin"),
        include_system_site_packages=False,
        created_by_uv=True,
    )


async def test_venvs_are_listed(monkeypatch):
    monkeypatch.setattr(
        "lazyvenv.app.find_venvs",
        lambda directory=None: [fake_venv(".venv"), fake_venv("env")],
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        venv_list = app.query_one("#venvs", ListView)
        assert len(venv_list.children) == 2


async def test_highlight_updates_details(monkeypatch):
    monkeypatch.setattr(
        "lazyvenv.app.find_venvs",
        lambda directory=None: [fake_venv(".venv"), fake_venv("env")],
    )
    app = LazyVenvApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()

        venv_list = app.query_one("#venvs", ListView)
        details = app.query_one("#details", Label)
        assert venv_list.index is not None
        assert app.venvs[venv_list.index].name in str(details.render())
