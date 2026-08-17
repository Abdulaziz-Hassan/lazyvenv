import shutil
import sys
from pathlib import Path

import pytest

from lazyvenv.create import _parse_interpreters, create_venv

UV_LIST_OUTPUT = """\
cpython-3.14.0rc1-linux-x86_64-gnu    /opt/uv/cpython-3.14.0rc1/bin/python3.14
cpython-3.13.6-linux-x86_64-gnu       /home/user/.local/bin/python3.13 -> /opt/uv/cpython-3.13.6/bin/python3.13
cpython-3.13.6-linux-x86_64-gnu       /opt/uv/cpython-3.13.6/bin/python3.13
pypy-3.10.16-linux-x86_64-gnu         /opt/uv/pypy-3.10.16/bin/pypy3
"""


def test_parse_interpreters():
    interpreters = _parse_interpreters(UV_LIST_OUTPUT)

    # newest first; rc versions sort above older stable ones
    assert [i.version for i in interpreters] == [
        "3.14.0rc1",
        "3.13.6",
        "3.13.6",
        "3.10.16",
    ]
    assert interpreters[0].implementation == "cpython"
    assert interpreters[3].implementation == "pypy"
    # symlink notation: the path before " -> " is used
    assert interpreters[1].path == Path("/home/user/.local/bin/python3.13")


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_create_venv_for_real(tmp_path):
    """End-to-end: uv must create a real venv with the current interpreter."""
    create_venv("created-by-test", Path(sys.executable), tmp_path)

    assert (tmp_path / "created-by-test" / "pyvenv.cfg").is_file()
