# Agent setup

One shared base for Claude Code and Codex on a Mac: settings, hooks, plugins, skills, and the tools the machine needs. It installs `qp-skills` for personal defaults and workflows.

**How to use it:** install Claude Code or Codex, open it, and give it this repo link. The agent checks what your machine has, tells you what it would add or change, and asks before it touches your own files. It installs the other CLI if it is missing.

**What you keep:** your own settings, plugins, and instructions. The agent backs up each file before it changes it, and it never removes what you own without asking.

**What is here:** `base/` holds the setup (plugins, skills, hooks, toolkit, and a starter for personal instructions). `steps/` holds the scripts the agent runs. `examples/` holds optional personal text. Roll a file back from `~/.agent-setup/backups/`.

## For the agent

Goal: this machine runs the base setup for Claude Code and Codex, and the user's own setup stays.

1. **Detect.** Find what exists: tools, plugins, skills, hooks, instruction files. `mise run plan` shows the file diff against `base/`.
2. **Recommend.** Group the findings as add / update / keep. Never remove what the user owns.
3. **Do.** After the user agrees, install only what is missing, apply the files (back up first), and refresh plugins and skills. Use `steps/` when it fits.
4. **SIGIDI.** If no `SIGIDI*.app` is in `/Applications` (and the Mac is arm64), install the latest arm64 DMG from the pre-release builds of `quantipixels/sigidi-release`.
5. **Verify.** Run `mise run doctor`. Fix what fails, or report the exact error.
6. **Personal defaults.** Once the machine is ready and `qp-skills` is installed, tell the user to ask their agent to **“set me up”**. This is qp-skills’ setup path for defaults and a retrospective.
7. **Scan.** Read-only. Look in the Claude, Codex, and tool setup for stale or duplicate items, broken paths, leftover temp and cache folders, outdated tools, and secrets in config. Change nothing; end with recommended cleanups, each with its reason and exact command.

Hook rows in `base/hooks.yaml` can declare `requires: [program, ...]`. Setup and apply install missing hook programs through the same mise path as toolkit tools, then enable only hooks whose requirements are on PATH. An unavailable program skips its hook with a reason and install command; offline mode skips installation. Plan and `--dry-run` show missing requirements without installing or writing. Doctor and check-tools report missing requirements of installed hooks, including in the offline structural profile. Program names map to the tools declared in `mise.toml` (for example, `python3` maps to `python`).

Pause for edits to the user's instruction or settings files, removals, logins (`claude auth login`, `codex login`, `gh auth login`), `sudo`, and choices between the user's version and the base. Codex plugins marked `login: true` install only after `codex login`.

Done when doctor passes and the report lists what changed, what was skipped, available updates, the scan's recommendations, and what the user still has to do. Tell the user to start new Claude Code and Codex sessions so the files load.

## Personal instructions and project tools

`qp-skills` replaces the retired `alarina` plugin. Its `asami` skill owns personal defaults in one source, `~/.agents/AGENTS.md`; its `asoju` skill owns models and delegation rules. Agent-setup seeds the source from `base/shared/instructions.md` (two lines on how to talk) only when missing, and never overwrites an existing source.

Codex reads `~/.codex/AGENTS.md` through a symlink to the source; Claude Code reads it through the first line `@~/.agents/AGENTS.md` in `~/.claude/CLAUDE.md`. Claude-only lines may follow the import and are kept. Existing host instruction files that need replacement require `--yes` after approval and are backed up under `~/.agent-setup/backups/`. `mise run plan`, `steps/apply --dry-run`, and `steps/setup --dry-run` show the changes and backups without writing. Doctor checks this layout.

Removing a plugin or skill from the base stops installing it; it does not uninstall it. Doctor warns about an installed retired `alarina` plugin and gives its removal command; that warning does not fail the check.

The `tech-stack` skill owns per-project tool choices. Project-specific decisions belong in the project.

Setup scans `~/Projects` up to two directory levels deep, skipping dependency and build folders, and installs missing toolchains for the build files it finds (JDK/Maven/Gradle, Node/pnpm, uv, Flutter, Rust, or Elixir/Erlang). A Gradle wrapper supplies Gradle. Project `.tool-versions` and `mise.toml` pins take precedence over Java versions declared in Maven or Gradle; differing pins are installed side by side, otherwise missing tools use `latest`. Use `--projects <dir>` (repeatable) on `steps/diff`, `steps/setup`, `steps/apply`, or `steps/doctor` to replace the default root. Plan and `--dry-run` list projects, requirements and install commands without writing or installing; apply/setup require `--yes` after approval, offline mode skips installs, and full-profile doctor checks only the scanned projects.

Read-only steps require `yq` on PATH; if it is missing, install it first with `mise install yq` after approval.

Agents should run a repository's own check command (for example, `npm run check`, `mise run check`, or `uv run ...`) rather than system Python; `uv` is installed to run Python checks with the dependencies the repository declares.

## Non-goals

- Agent-setup does not store credentials, history, sessions, plugin caches, or MCP OAuth data in this repository.
- It does not own the user's instruction text or model set; qp-skills owns those defaults. Host settings remain machine configuration.
- It does not choose project tools; it installs only what the machine needs.
- Checks run locally; there is no hosted CI.

## Contributing

Run `mise install`, `mise run hooks:install`, then `mise run check` (ShellCheck, gitleaks, tests). See `AGENTS.md` for the rules for this repo.
