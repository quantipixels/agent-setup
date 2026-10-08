# Agent setup

Set up Claude Code and Codex on a Mac from one base: instructions, settings, hooks, plugins, skills, and Codex agent roles. Give an agent this repo link. It detects what the machine has, recommends changes, and asks you only where the choice is yours.

## For the agent

Goal: this machine runs the base setup for Claude Code and Codex, with the user's own setup kept.

1. **Detect.** Find the tools, plugins, skills, hooks, and instruction files that exist now. `mise run plan` shows the file diff against the base.
2. **Recommend.** List what is missing, what differs from the base, and what is outdated, grouped as add / update / keep. Never remove what the user owns.
3. **Do.** After the user agrees, install only what is missing, apply the files (a backup goes to `~/.agent-setup/backups/<date>/` first), and refresh plugins and skills. Use the `steps/` scripts when they fit. When the machine needs another path, take it and say why.
4. **Verify.** Run `mise run doctor`. Fix what fails, or report the exact error.

Ask the user for the name the agents should use (`--name`, default: `git config user.name`). Pause for: changes to the user's instruction or settings files, removals, logins (`! gh auth login`, `claude auth login`, `codex login`), `sudo`, and choices between the user's version and the base. Codex `@openai-curated` plugins install only after `codex login`.

Done when: doctor passes, and the report lists what changed, what was skipped, the available updates, and what the user still has to do.

Start a new Claude Code and Codex session after setup, so the new files load.

## Toolkit

| Language | Tool | Why |
| --- | --- | --- |
| Always | rg, fd, jq, ast-grep, lefthook, gitleaks, mise | Search, inspect JSON, match code, run checks, find secrets, manage tools |
| TS | typescript-lsp, Vite+ (`vp`), oxlint, oxfmt | Code intelligence; Vite+ toolchain with Oxc lint and format |
| Python | pyright-lsp, ruff | Code intelligence, format and lint |
| Kotlin/Java | kotlin-lsp, jdtls-lsp | Code intelligence |
| Rust | rust-analyzer-lsp | Code intelligence |
| Swift | swift-lsp, swiftui-pro | Code intelligence and SwiftUI review |
| Shell | shellcheck, shfmt | Check and format shell |

Run `mise run toolkit` for the install step. LSP names are Claude plugins; language servers also need their own runtime. Swift needs Xcode Command Line Tools: pause, then the person runs `xcode-select --install`. Install project runtimes through that project's mise configuration.

## Files and steps

`base/shared/instructions.md` supplies both instruction templates. Personal voice and the Alárinà usefulness log are opt-in in `examples/personal.md`. `base/skills.txt` contains source and skill name only, verified against installed folders. `base/codex/agents.pins.toml` holds role and model choices; these are not tool release pins.

`steps/check-tools`, `render`, `diff`, `apply`, `plugins`, `skills`, `codex-agents`, `toolkit`, `doctor`, and `capture` can run separately. `steps/setup` runs the sequence. Render prints to stdout by default. Use each step's `--help` for options.

Capture only the allowed setup files, after reviewing them for secrets. `mise run capture -- --output local/capture` must not copy auth, tokens, history, sessions, caches or MCP OAuth data. Review its output before sharing it. Optional inactive Codex hooks which use `tldr` are carried as source only; setup does not activate them. The machine-local `dcg` command and app-bundled runtime paths are excluded because this base does not install them.

To roll back a file, choose its backup under `~/.agent-setup/backups/` and copy it to the original relative path after reviewing the diff. Keep credentials out of rollback. Use the recorded versions in `last-good.lock` only if you deliberately choose to restore a prior tool release.

## Checks

```sh
mise install
mise run hooks:install
mise run check
```

CI runs on macOS for pull requests, pushes and each night. It runs the checks, plans a scratch install, applies it with no login, and runs doctor. It does not establish authenticated agent behavior.

Install commands follow the [Claude plugin CLI](https://code.claude.com/docs/en/plugins-reference), [Codex plugin CLI source](https://github.com/openai/codex/blob/main/codex-rs/cli/src/plugin_cmd.rs), and [skills CLI](https://github.com/vercel-labs/skills). Mise tasks disable automatic installs. The direct `steps/diff` is read-only; mise can still create cache metadata before it starts the task. Setup performs explicit latest installs. This differs from the usual tech-stack wrapper rule because installation is this repo's purpose.
