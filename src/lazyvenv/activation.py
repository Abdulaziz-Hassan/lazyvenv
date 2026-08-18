from lazyvenv.venvs import Venv

DEACTIVATE_COMMAND = "deactivate"


def activation_command(venv: Venv) -> str:
    """The shell command that activates *venv* in the current shell."""
    return f"source {venv.path}/bin/activate"


_INIT_SCRIPT = """\
lazyvenv() {
    local tmpfile
    tmpfile="$(mktemp "${TMPDIR:-/tmp}/lazyvenv.XXXXXX")"
    LAZYVENV_SHELL_CMD_FILE="$tmpfile" command lazyvenv "$@"
    if [ -s "$tmpfile" ]; then
        eval "$(cat "$tmpfile")"
    fi
    rm -f "$tmpfile"
}
"""


def init_script(shell: str) -> str:
    """The wrapper function for *shell* for ``eval "$(lazyvenv init zsh)"``."""
    if shell not in {"zsh", "bash"}:
        raise ValueError(f"unsupported shell: {shell!r} (supported: zsh, bash)")
    return _INIT_SCRIPT
