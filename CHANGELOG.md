# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project uses
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-09-12

### Fixed

- Broken virtual environments (e.g. an interpreter that was removed) are
  now marked in the list and explained in the details pane, can no longer be
  activated, and report a clear message instead of an error
- Package read failures (unrunnable interpreter, timeout, unreadable
  site-packages) now show the reason in the packages pane instead of an
  error toast

### Changed

- `lazyvenv init` also accepts `sh`

## [0.1.0] - 2026-09-06

First release.

### Added

- TUI listing virtual environments found in the current directory, with
  active/pending status markers and Python versions
- Details pane per venv: path, disk size, base interpreter, creator tool
- Packages table per venv with installed distributions
- Package metadata pane and a full detail screen: license, author, homepage,
  install origin (registry/wheel/sdist/local/editable/vcs), installer,
  dependencies
- Create new venvs from any uv-managed interpreter
- Delete venvs with a confirmation dialog
- Activate/deactivate venvs in the parent shell via the shell hook
  (`eval "$(lazyvenv init zsh)"`)
- Filter packages by name with `/`
- Vim-style navigation (`j`/`k`/`h`/`l`)
- CLI: `lazyvenv`, `lazyvenv init [shell]`, `--help`, `--version`

[0.1.1]: https://github.com/Abdulaziz-Hassan/lazyvenv/releases/tag/v0.1.1
[0.1.0]: https://github.com/Abdulaziz-Hassan/lazyvenv/releases/tag/v0.1.0
