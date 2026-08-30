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

packages = []
for dist in md.distributions():
    meta = dist.metadata
    home_page = meta.get("Home-page") or ""
    if not home_page:
        project_urls = meta.get_all("Project-URL") or []
        if project_urls:
            home_page = project_urls[0].split(",")[-1].strip()
    raw_url = dist.read_text("direct_url.json")
    packages.append(
        {
            "name": dist.name,
            "version": dist.version,
            "summary": meta.get("Summary") or "",
            "license": meta.get("License-Expression") or meta.get("License") or "",
            "author": (
                meta.get("Author") or meta.get("Maintainer") or meta.get("Author-email") or ""
            ),
            "home_page": home_page,
            "requires": dist.requires or [],
            "installer": (dist.read_text("INSTALLER") or "").strip() or None,
            "direct_url": json.loads(raw_url) if raw_url else None,
        }
    )
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

    packages = []
    for item in raw:
        origin, source_url = _classify_origin(
            item["installer"] or "", item["direct_url"]
        )
        packages.append(
            Package(
                name=item["name"],
                version=item["version"],
                summary=item["summary"],
                license=item["license"],
                author=item["author"],
                home_page=item["home_page"],
                requires=tuple(item["requires"]),
                installer=item["installer"] or "",
                origin=origin,
                source_url=source_url,
            )
        )
    return sorted(packages, key=lambda p: p.name.lower())


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
