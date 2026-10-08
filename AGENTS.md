# Working in this repo

This repo sets up Claude Code and Codex on a Mac. `README.md` is the runbook an agent follows; `steps/` are the tools it uses; `base/` is the setup it installs.

- Write step entry points in POSIX `sh` and file work in `steps/engine.py` with the Python 3.11+ standard library. No third-party packages.
- Setup lists live in `base/*.yaml` (plugins, skills, hooks, toolkit, agents), read through `yq -o=json`; keep them to maps, lists, strings, and bools.
- Tools, plugins, and skills install at the latest version. `last-good.lock` is for rollback only, never an install source.
- Keep `plan` and `--dry-run` free of writes and installs.
- Merge JSON and TOML: base keys win, keys the host added stay. Stop on a malformed live file; never discard it to make doctor pass.
- Never store credentials, history, sessions, plugin caches, or MCP OAuth data. Personal content goes in `examples/`.
- Before you commit, run `mise run check` (ShellCheck, gitleaks, tests).
