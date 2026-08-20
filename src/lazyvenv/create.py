"""Create virtual environments and list interpreters, via uv."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class UvCommandError(Exception):
    """Raised when a uv command fails."""


@dataclass(frozen=True)
class Interpreter:
    """A Python interpreter known to uv."""

    version: str
    implementation: str
    path: Path

    @property
    def display_path(self) -> str:
        """The path with the user's home directory collapsed to ~."""
        try:
            return f"~/{self.path.relative_to(Path.home())}"
        except ValueError:
            return str(self.path)

    @property
    def label(self) -> str:
        """Human-readable text for the interpreter picker."""
        return f"{self.implementation} {self.version} — {self.display_path}"


def list_interpreters() -> list[Interpreter]:
    """Return the interpreters installed on this machine, newest first."""
    result = _run_uv(["python", "list", "--only-installed"])
    return _dedupe(_parse_interpreters(result.stdout))


def _dedupe(interpreters: list[Interpreter]) -> list[Interpreter]:
    """Drop entries that are symlinks to the same binary, keeping the shortest path for display."""
    by_resolved: dict[Path, Interpreter] = {}
    for interpreter in interpreters:
        key = interpreter.path.resolve()
        existing = by_resolved.get(key)
        if existing is None or len(str(interpreter.path)) < len(str(existing.path)):
            by_resolved[key] = interpreter
    return list(by_resolved.values())


def create_venv(name: str, python_path: Path, directory: Path) -> None:
    """Create a venv named *name* inside *directory* with *python_path*."""
    _run_uv(["venv", "--python", str(python_path), name], cwd=directory)


def _parse_interpreters(output: str) -> list[Interpreter]:
    """Parse ``uv python list`` output into interpreters."""
    interpreters = []
    for line in output.splitlines():
        if not line.strip():
            continue
        key, path = line.split(maxsplit=1)
        implementation, version = key.split("-", maxsplit=2)[:2]
        real_path = path.split(" -> ")[0]  # use the symlink path itself
        interpreters.append(Interpreter(version, implementation, Path(real_path)))
    return sorted(interpreters, key=lambda i: _version_key(i.version), reverse=True)


def _version_key(version: str) -> tuple[int, ...]:
    """Turn ``"3.13.6"`` into ``(3, 13, 6)`` for correct numeric sorting."""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def _run_uv(
    args: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a uv command, raising :class:`UvCommandError` on failure."""
    try:
        return subprocess.run(
            ["uv", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
    except OSError as error:
        raise UvCommandError(f"cannot run uv: {error}") from error
    except subprocess.CalledProcessError as error:
        raise UvCommandError(error.stderr.strip()) from error
