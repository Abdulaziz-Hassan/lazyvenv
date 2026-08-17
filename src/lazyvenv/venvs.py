"""Discovery of Python virtual environments.

A directory is a virtual environment if (and only if) it contains a
``pyvenv.cfg`` file at its root - that file is the canonical fingerprint
defined by PEP 405. It also records which interpreter and which tool
created the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PYVENV_CFG = "pyvenv.cfg"


@dataclass(frozen=True)
class Venv:
    """A virtual environment found on disk."""

    path: Path
    python_version: str
    home: Path
    include_system_site_packages: bool
    created_by_uv: bool

    @property
    def name(self) -> str:
        """The venv's directory name."""
        return self.path.name

    @property
    def python(self) -> Path:
        """The venv's own interpreter binary."""
        return self.path / "bin" / "python"

    @property
    def is_active(self) -> bool:
        """Whether this venv is the currently activated one."""
        active = os.environ.get("VIRTUAL_ENV")
        return active is not None and Path(active) == self.path


def find_venvs(directory: Path | None = None) -> list[Venv]:
    """Find virtual environments directly inside *directory* (default: cwd)."""
    root = (directory or Path.cwd()).resolve()
    candidates = [root, *(child for child in root.iterdir() if child.is_dir())]

    venvs = [
        _venv_from_dir(candidate) for candidate in candidates if _is_venv(candidate)
    ]
    return sorted(venvs, key=lambda v: v.name)


def _is_venv(path: Path) -> bool:
    """Check whether *path* is a venv, tolerating unreadable directories."""
    try:
        return (path / PYVENV_CFG).is_file()
    except OSError:
        return False


def _venv_from_dir(path: Path) -> Venv:
    """Build a :class: `Venv` from a directory containing a pyvenv.cfg."""
    config = _parse_pyvenv_cfg(path / PYVENV_CFG)
    return Venv(
        path=path,
        python_version=config.get("version") or config.get("version_info", "unknown"),
        home=Path(config.get("home", "")),
        include_system_site_packages=config.get(
            "include-system-site-packages", ""
        ).lower()
        == "true",
        created_by_uv="uv" in config,
    )


def _parse_pyvenv_cfg(cfg_path: Path) -> dict[str, str]:
    """Parse ``pyvenv.cfg`` into a dict."""
    config: dict[str, str] = {}
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            config[key.strip()] = value.strip()
    return config
