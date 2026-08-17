"""Read the packages installed in a virtual environment."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from lazyvenv.venvs import Venv

_INSPECT_SCRIPT = """
import importlib.metadata as md
import json

packages = [
    {
        "name": dist.name,
        "version": dist.version,
        "summary": dist.metadata.get("Summary") or "",
    }
    for dist in md.distributions()
]
print(json.dumps(packages))
"""


class PackageInspectionError(Exception):
    """Raised when a venv's packages cannot be read."""


@dataclass(frozen=True)
class Package:
    """A distribution installed in a venv."""

    name: str
    version: str
    summary: str


def list_packages(venv: Venv, timeout: float = 10) -> list[Package]:
    """Return the packages installed in a *venv*, sorted by name."""
    try:
        result = subprocess.run(
            [venv.python, "-c", _INSPECT_SCRIPT],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        raw = json.loads(result.stdout)
    except OSError as error:
        raise PackageInspectionError(f"cannot run {venv.python}: {error}") from error
    except subprocess.CalledProcessError as error:
        raise PackageInspectionError(error.stderr.strip()) from error
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        raise PackageInspectionError(str(error)) from error

    packages = [Package(**item) for item in raw]
    return sorted(packages, key=lambda p: p.name.lower())
