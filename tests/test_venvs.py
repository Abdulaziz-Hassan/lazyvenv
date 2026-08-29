import platform
from pathlib import Path
from venv import EnvBuilder

from lazyvenv.venvs import collapse_home, delete_venv, find_venvs

STDLIB_CFG = """\
home = /usr/bin
include-system-site-packages = false
version = 3.13.6
"""

UV_CFG = """\
home = /home/user/.local/share/uv/python/cpython-3.13.6-linux-x86_64-gnu/bin
implementation = CPython
uv = 0.12.1
version_info = 3.13.6
include-system-site-packages = false
"""


def make_venv(parent: Path, name: str, cfg: str = STDLIB_CFG) -> Path:
    """Create a fake venv: a directory containing only a pyvenv.cfg."""
    venv_dir = parent / name
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text(cfg)
    return venv_dir


def test_find_venvs_discovers_and_parses(tmp_path):
    make_venv(tmp_path, ".venv")
    make_venv(tmp_path, "env", cfg=UV_CFG)
    (tmp_path / "not-a-venv").mkdir()  # no pyvenv.cfg → must be ignored

    found = find_venvs(tmp_path)

    assert [v.name for v in found] == [".venv", "env"]
    stdlib_venv, uv_venv = found
    assert stdlib_venv.python_version == "3.13.6"
    assert stdlib_venv.home == Path("/usr/bin")
    assert stdlib_venv.include_system_site_packages is False
    assert stdlib_venv.created_by_uv is False
    assert uv_venv.python_version == "3.13.6"
    assert uv_venv.created_by_uv is True


def test_find_venvs_checks_directory_itself(tmp_path):
    (tmp_path / "pyvenv.cfg").write_text(STDLIB_CFG)

    found = find_venvs(tmp_path)

    assert [v.name for v in found] == [tmp_path.name]


def test_is_active_matches_virtual_env_var(tmp_path, monkeypatch):
    make_venv(tmp_path, ".venv")
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / ".venv"))

    (found,) = find_venvs(tmp_path)

    assert found.is_active


def test_against_real_venv(tmp_path):
    """End-to-end: parse a venv created by the real stdlib venv module."""
    EnvBuilder(with_pip=False).create(tmp_path / "real")

    (found,) = find_venvs(tmp_path)

    assert found.python_version == platform.python_version()
    assert found.python.exists()


def test_find_venvs_skips_unreadable_directories(tmp_path):
    make_venv(tmp_path, ".venv")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)  # no read/execute permission, like other users' /tmp dirs
    try:
        found = find_venvs(tmp_path)
    finally:
        locked.chmod(0o755)  # restore so pytest can delete tmp_path afterwards
    assert [v.name for v in found] == [".venv"]


def test_collapse_home():
    assert collapse_home(Path.home() / "proj" / ".venv") == "~/proj/.venv"
    assert collapse_home(Path("/usr/bin/python3")) == "/usr/bin/python3"


def test_delete_venv_removes_the_directory(tmp_path):
    venv_dir = make_venv(tmp_path, ".venv")
    (found,) = find_venvs(tmp_path)

    delete_venv(found)

    assert not venv_dir.exists()
