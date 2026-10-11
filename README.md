# Agent setup

One shared base for Claude Code and Codex on a Mac: instructions, settings, hooks, plugins, skills, and a toolkit of dev tools.

**How to use it:** install Claude Code or Codex, open it, and give it this repo link. The agent checks what your machine has, tells you what it would add or change, and asks before it touches your own files. It installs the other CLI if it is missing.

**What you keep:** your own settings, plugins, and instructions. The agent backs up each file before it changes it, and it never removes what you own without asking.

**What is here:** `base/` holds the setup (plugins, skills, hooks, toolkit, instruction templates). `steps/` holds the scripts the agent runs. `examples/` holds optional personal text. Roll a file back from `~/.agent-setup/backups/`.

## For the agent

Goal: this machine runs the base setup for Claude Code and Codex, and the user's own setup stays.

1. **Detect.** Find what exists: tools, plugins, skills, hooks, instruction files. `mise run plan` shows the file diff against `base/`.
2. **Recommend.** Group the findings as add / update / keep. Never remove what the user owns.
3. **Do.** After the user agrees, install only what is missing, apply the files (back up first), and refresh plugins and skills. Use `steps/` when it fits.
4. **SIGIDI.** If no `SIGIDI*.app` is in `/Applications` (and the Mac is arm64), install the latest arm64 DMG from the pre-release builds of `quantipixels/sigidi-release`.
5. **Engineering workflow.** Install `qp-skills` from `quantipixels/skills` for each host. Restart the host and confirm its `alarina` skill loads. Keep `tech-stack` as the standards source.
6. **Verify.** Run `mise run doctor`. Fix what fails, or report the exact error.
7. **Scan.** Read-only. Look in the Claude, Codex, and tool setup for stale or duplicate items, broken paths, leftover temp and cache folders, outdated tools, and secrets in config. Change nothing; end with recommended cleanups, each with its reason and exact command.

Ask for the name the agents should use (`--name`, default `git config user.name`). Pause for edits to the user's instruction or settings files, removals, logins (`claude auth login`, `codex login`, `gh auth login`), `sudo`, and choices between the user's version and the base. Codex plugins marked `login: true` install only after `codex login`.

Done when doctor passes and the report lists what changed, what was skipped, available updates, the scan's recommendations, and what the user still has to do. Tell the user to start new Claude Code and Codex sessions so the files load.

## Engineering workflow setup

QP Skills is the default engineering plugin on Claude Code and Codex; tech-stack supplies tooling and quality-gate standards. The `alarina` skill inside qp-skills is the workflow router, not the separate `alarina@alarina` plugin.

For an existing installation, preserve the user's plugins, records and configuration. Report a separately installed Alárinà plugin as a possible duplicate; do not remove it without approval. The current qp-skills package has no `idasile` setup skill, so installation does not perform Alárinà migration, project linking or configuration. Report any such requested work as pending rather than claiming `alarina setup` ran.

If qp-skills installation or loading fails, record the exact command and error, continue unaffected steps, and report engineering setup as incomplete. Do not silently substitute another plugin or make doctor pass by changing the base lists.

## Contributing

Run `mise install`, `mise run hooks:install`, then `mise run check` (ShellCheck, gitleaks, tests). Checks run locally; there is no hosted CI. See `AGENTS.md` for the rules for this repo.
