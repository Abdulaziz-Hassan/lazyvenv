from pathlib import Path
from venv import EnvBuilder

import pytest

from lazyvenv.packages import PackageInspectionError, _classify_origin, list_packages
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
    """A venv created with pip must report pip with rich metadata."""
    EnvBuilder(with_pip=True).create(tmp_path / "real")
    venv = make_venv_object(tmp_path / "real")

    packages = list_packages(venv)

    names = [package.name for package in packages]
    assert names == sorted(names, key=str.lower)
    pip = packages[names.index("pip")]
    assert pip.installer == "pip"
    assert pip.license
    assert pip.author
    assert pip.requires == ()
    assert pip.origin


def test_list_packages_broken_venv(tmp_path):
    """A venv whose interpreter is gone raises PackageInspectionError."""
    venv = make_venv_object(tmp_path / "ghost")  # nothing exists on disk

    with pytest.raises(PackageInspectionError):
        list_packages(venv)


@pytest.mark.parametrize(
    ("installer", "direct_url", "expected_kind"),
    [
        ("", None, "unknown"),
        ("uv", None, "registry"),
        (
            "pip",
            {
                "url": "https://files.pythonhosted.org/x/r-2.3-py3-none-any.whl",
                "archive_info": {},
            },
            "wheel",
        ),
        (
            "pip",
            {
                "url": "https://files.pythonhosted.org/x/r-2.3.tar.gz",
                "archive_info": {},
            },
            "sdist",
        ),
        (
            "uv",
            {"url": "file:///home/user/requests", "dir_info": {"editable": True}},
            "editable",
        ),
        ("pip", {"url": "file:///home/user/requests", "dir_info": {}}, "local"),
        (
            "pip",
            {"url": "https://github.com/psf/requests", "vcs_info": {"vcs": "git"}},
            "vcs (git)",
        ),
    ],
)
def test_classify_origin(installer, direct_url, expected_kind):
    kind, _source_url = _classify_origin(installer, direct_url)
    assert kind == expected_kind
