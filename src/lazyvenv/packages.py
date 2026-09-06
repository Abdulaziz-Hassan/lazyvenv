"""Read the packages installed in a virtual environment."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from lazyvenv.venvs import Venv

_INSPECT_SCRIPT = """
import importlib.metadata as md
import json

packages = [
    {
        "name": dist.name,
        "version": dist.version,
        "metadata": dict(dist.metadata),
        "project_urls": dist.metadata.get_all("Project-URL") or [],
        "requires": dist.requires or [],
        "installer": (dist.read_text("INSTALLER") or "").strip() or None,
        "direct_url": json.loads(raw) if (raw := dist.read_text("direct_url.json")) else None,
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
    license: str
    author: str
    home_page: str
    requires: tuple[str, ...]
    installer: str
    origin: str
    source_url: str


def list_packages(venv: Venv, timeout: float = 10) -> list[Package]:
    """Return the packages installed in *venv*, sorted by name."""
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

    return sorted((_to_package(item) for item in raw), key=lambda p: p.name.lower())


def _to_package(item: dict[str, Any]) -> Package:
    """Turn one raw probe result into a :class:`Package`."""
    metadata: dict[str, str] = item["metadata"]
    installer = item["installer"] or ""
    origin, source_url = _classify_origin(installer, item["direct_url"])
    return Package(
        name=item["name"],
        version=item["version"],
        summary=metadata.get("Summary", ""),
        license=metadata.get("License-Expression") or metadata.get("License", ""),
        author=(
            metadata.get("Author")
            or metadata.get("Maintainer")
            or metadata.get("Author-email", "")
        ),
        home_page=_home_page(metadata, item["project_urls"]),
        requires=tuple(item["requires"]),
        installer=installer,
        origin=origin,
        source_url=source_url,
    )


def _home_page(metadata: dict[str, str], project_urls: list[str]) -> str:
    """The package's homepage: ``Home-page``, else the first ``Project-URL``."""
    if home_page := metadata.get("Home-page"):
        return home_page
    if project_urls:
        return project_urls[0].split(",")[-1].strip()  # "Docs, https://…" → URL
    return ""


def _classify_origin(
    installer: str, direct_url: dict[str, Any] | None
) -> tuple[str, str]:
    """Classify how a distribution was installed."""
    if direct_url is None:
        return ("registry", "") if installer else ("unknown", "")
    url = direct_url.get("url", "")
    if "dir_info" in direct_url:
        kind = "editable" if direct_url["dir_info"].get("editable") else "local"
    elif "vcs_info" in direct_url:
        kind = f"vcs ({direct_url['vcs_info'].get('vcs', '?')})"
    elif url.endswith(".whl"):
        kind = "wheel"
    else:
        kind = "sdist"
    return kind, url
