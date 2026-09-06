import sys

import pytest

from lazyvenv import main


def test_help_prints_usage(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lazyvenv", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert "usage: lazyvenv" in capsys.readouterr().out


def test_version_prints_the_version(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lazyvenv", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.startswith("lazyvenv ")


def test_unknown_command_exits_with_usage(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lazyvenv", "bogus"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    assert "invalid choice: 'bogus'" in capsys.readouterr().err


def test_init_prints_the_wrapper(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lazyvenv", "init"])

    main()

    assert "lazyvenv()" in capsys.readouterr().out


def test_init_rejects_unknown_shells(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["lazyvenv", "init", "fish"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    assert "invalid choice: 'fish'" in capsys.readouterr().err
