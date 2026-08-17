from pathlib import Path
from venv import EnvBuilder

import pytest

from lazyvenv.packages import PackageInspectionError, list_packages
from lazyvenv.venvs import Venv


def make_venv_object(path: Path) -> Venv:
    """A Venv pointing at *path* with dummy metadata."""
    return Venv(
        path=path,
        python_version="3.13.6",
        home=Path("/usr/bin"),
        include_system_site_packages=False,
        created_by_uv=False,
    )


def test_list_packages_on_real_venv(tmp_path):
    """A venv created with pip must report pip as installed."""
    EnvBuilder(with_pip=True).create(tmp_path / "real")
    venv = make_venv_object(tmp_path / "real")

    packages = list_packages(venv)

    names = [package.name for package in packages]
    assert "pip" in names
    assert names == sorted(names, key=str.lower)
    assert packages[names.index("pip")].summary


def test_list_packages_broken_venv(tmp_path):
    """A venv whose interpreter is gone raises PackageInspectionError."""
    venv = make_venv_object(tmp_path / "ghost")  # nothing exists on disk

    with pytest.raises(PackageInspectionError):
        list_packages(venv)
