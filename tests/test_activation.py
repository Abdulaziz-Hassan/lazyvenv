from pathlib import Path

import pytest

from lazyvenv.activation import activation_command, init_script
from lazyvenv.venvs import Venv

FAKE_VENV = Venv(
    path=Path("/fake/.venv"),
    python_version="3.13.6",
    home=Path("/usr/bin"),
    include_system_site_packages=False,
    created_by_uv=False,
)


def test_activation_command_points_at_the_venvs_activate_script():
    assert activation_command(FAKE_VENV) == "source '/fake/.venv/bin/activate'"


def test_activation_command_quotes_hostile_paths():
    """A venv name with shell metacharacters must stay inside the quotes."""
    hostile = Venv(
        path=Path("/tmp/$(touch pwned)"),
        python_version="3.13.6",
        home=Path("/usr/bin"),
        include_system_site_packages=False,
        created_by_uv=False,
    )

    command = activation_command(hostile)

    assert command == "source '/tmp/$(touch pwned)/bin/activate'"
    assert command.count("'") == 2  # the whole path is inside one quoted span


def test_init_script_contains_the_wrapper_machinery():
    script = init_script("zsh")
    assert "LAZYVENV_SHELL_CMD_FILE" in script
    assert "eval" in script
    assert "command lazyvenv" in script


def test_init_script_rejects_unknown_shells():
    with pytest.raises(ValueError, match="unsupported shell"):
        init_script("fish")


def test_init_script_mktemp_template_is_valid():
    script = init_script("zsh")
    (mktemp_line,) = [line for line in script.splitlines() if "mktemp" in line]
    assert "XXXXXX" in mktemp_line
