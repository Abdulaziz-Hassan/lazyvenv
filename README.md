# lazyvenv

[![PyPI](https://img.shields.io/pypi/v/lazyvenv)](https://pypi.org/project/lazyvenv/)
[![Python](https://img.shields.io/pypi/pyversions/lazyvenv)](https://pypi.org/project/lazyvenv/)
[![CI](https://github.com/Abdulaziz-Hassan/lazyvenv/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdulaziz-Hassan/lazyvenv/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A TUI for managing Python virtual environments.

![screenshot](https://raw.githubusercontent.com/Abdulaziz-Hassan/lazyvenv/main/docs/screenshot.png)

lazyvenv shows the virtual environments in the current directory, lets you
inspect their installed packages (including origin, size, and metadata), and
create, delete, activate, and deactivate environments — all from one keyboard-
driven interface.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) — used to list interpreters and create venvs
- zsh, bash, or sh (for the activation shell hook)

## Install

```bash
uv tool install lazyvenv
```

This installs the `lazyvenv` command globally, outside any project venv —
which is required for activation to work reliably.

## Shell integration (for activation)

Pressing `a` inside the app marks a venv to be (de)activated, and the change
is applied when you quit. For that to work, add the wrapper function to your
shell config:

```bash
# ~/.zshrc or ~/.bashrc
eval "$(lazyvenv init zsh)"   # or: lazyvenv init bash
```

Restart your shell (or `source` the file). Without this hook the app still
works, but `a` will show a warning instead of activating.

## Usage

Run `lazyvenv` inside any directory containing virtual environments (it scans
the directory itself and its immediate children for `pyvenv.cfg` files):

```bash
cd your-project
lazyvenv
```

### Keys

| Key | Action |
|-----|--------|
| `j` / `k` | Move the cursor up/down (arrow keys work too) |
| `h` / `l` | Switch between the venv list and the packages table |
| `a` | Toggle (de)activation of the highlighted venv (applied on quit) |
| `c` | Create a new venv (pick any uv-managed interpreter) |
| `d` | Delete the highlighted venv (with confirmation) |
| `r` | Refresh the venv list |
| `/` | Filter packages by name (`Esc` clears) |
| `⏎` | Open the full details for the highlighted package |
| `q` | Quit (or go back, inside a screen/dialog) |

### CLI

```
lazyvenv               Launch the TUI
lazyvenv init [shell]  Print the shell wrapper (zsh or bash)
lazyvenv --version     Print the version
lazyvenv --help        Show help
```

## Development

```bash
git clone https://github.com/Abdulaziz-Hassan/lazyvenv
cd lazyvenv
uv sync
uv run pytest        # tests
uv run ruff check    # lint
uv run ruff format   # format
uv run mypy          # types (strict)
uv run lazyvenv      # run the app
```

For local development of the global command (e.g. to test the shell hook):

```bash
uv tool install --editable .
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
