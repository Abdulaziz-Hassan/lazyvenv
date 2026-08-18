from pathlib import Path

import pytest

from lazyvenv import main
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
    assert activation_command(FAKE_VENV) == "source /fake/.venv/bin/activate"


def test_init_script_contains_the_wrapper_machinery():
    script = init_script("zsh")
    assert "LAZYVENV_SHELL_CMD_FILE" in script
    assert "eval" in script
    assert "command lazyvenv" in script


def test_init_script_rejects_unknown_shells():
    with pytest.raises(ValueError, match="unsupported shell"):
        init_script("fish")


def test_activate_subcommand_prints_the_source_line(monkeypatch, capsys):
    monkeypatch.setattr("lazyvenv.find_venvs", lambda directory=None: [FAKE_VENV])
    monkeypatch.setattr("sys.argv", ["lazyvenv", "activate", ".venv"])

    main()

    assert capsys.readouterr().out == "source /fake/.venv/bin/activate\n"


def test_activate_subcommand_unknown_venv_exits(monkeypatch):
    monkeypatch.setattr("lazyvenv.find_venvs", lambda directory=None: [])
    monkeypatch.setattr("sys.argv", ["lazyvenv", "activate", "ghost"])

    with pytest.raises(SystemExit):
        main()


def test_init_script_mktemp_template_is_valid():
    script = init_script("zsh")
    (mktemp_line,) = [line for line in script.splitlines() if "mktemp" in line]
    assert "XXXXXX" in mktemp_line
