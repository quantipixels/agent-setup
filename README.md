# Agent setup

Set up Claude Code and Codex on a Mac from one base: instructions, settings, hooks, plugins, and skills. Give an agent this repo link. It detects what the machine has, recommends changes, and asks you only where the choice is yours.

**Before you start:** install Claude Code or Codex yourself, whichever you want to run the setup with. The agent detects the other one and installs it if it is missing.

## For the agent

Goal: this machine runs the base setup for Claude Code and Codex, with the user's own setup kept.

1. **Detect.** Find the tools, plugins, skills, hooks, and instruction files that exist now. `mise run plan` shows the file diff against the base.
2. **Recommend.** List what is missing, what differs from the base, and what is outdated, grouped as add / update / keep. Never remove what the user owns.
3. **Do.** After the user agrees, install only what is missing, apply the files (a backup goes to `~/.agent-setup/backups/<date>/` first), and refresh plugins and skills. Use the `steps/` scripts when they fit. When the machine needs another path, take it and say why.
4. **Set up Alárinà.** After the `alarina` plugin installs, run `alarina setup`. It sets up Alárinà's own agents and models, so this repo does not.
5. **Verify.** Run `mise run doctor`. Fix what fails, or report the exact error.
6. **Scan.** Do a quick, read-only scan of the user's Claude, Codex, and tool setup. Look for stale or duplicate plugins, skills, hooks, and instruction text; settings that point to missing files; leftover temp, backup, and cache folders; outdated or broken tools; and secrets in config files. Change nothing. End the report with a short list of recommended cleanups and fixes, each with its reason and the exact command, so the user can approve them one by one.

Ask the user for the name the agents should use (`--name`, default: `git config user.name`). Pause for: changes to the user's instruction or settings files, removals, logins (`! gh auth login`, `claude auth login`, `codex login`), `sudo`, and choices between the user's version and the base. Codex plugins marked `login: true` in `base/plugins.yaml` install only after `codex login`.

Done when: doctor passes, and the report lists what changed, what was skipped, the available updates, the recommended cleanups from the scan, and what the user still has to do.

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

`base/shared/instructions.md` supplies both instruction templates. Personal voice and the Alárinà usefulness log are opt-in in `examples/personal.md`. Setup lists live in YAML that names each host: `base/plugins.yaml` (plugins and marketplaces), `base/skills.yaml` (source and skill names, verified against installed folders), `base/hooks.yaml` (rendered into each host's native hook format; scripts stay in `base/<host>/hooks/`), and `base/toolkit.yaml`. The engine reads them through `yq`; it generates the hooks, `enabledPlugins` and `extraKnownMarketplaces` settings keys and `~/.codex/hooks.json`.

`steps/check-tools`, `render`, `diff`, `apply`, `plugins`, `skills`, `toolkit`, `doctor`, and `capture` can run separately. `steps/setup` runs the sequence. Render prints to stdout by default. Use each step's `--help` for options.

Capture only the allowed setup files, after reviewing them for secrets. `mise run capture -- --output local/capture` must not copy auth, tokens, history, sessions, caches or MCP OAuth data. Review its output before sharing it. Optional inactive Codex hooks which use `tldr` are carried as source only; setup does not activate them. The machine-local `dcg` command and app-bundled runtime paths are excluded because this base does not install them.

To roll back a file, choose its backup under `~/.agent-setup/backups/` and copy it to the original relative path after reviewing the diff. Keep credentials out of rollback. Use the recorded versions in `last-good.lock` only if you deliberately choose to restore a prior tool release.

## Checks

```sh
mise install
mise run hooks:install
mise run check
```

Checks run locally: `mise run check` and the lefthook hooks. There is no hosted CI, because setup needs the private `alarina` repo.

Install commands follow the [Claude plugin CLI](https://code.claude.com/docs/en/plugins-reference), [Codex plugin CLI source](https://github.com/openai/codex/blob/main/codex-rs/cli/src/plugin_cmd.rs), and [skills CLI](https://github.com/vercel-labs/skills). Mise tasks disable automatic installs. The direct `steps/diff` is read-only; mise can still create cache metadata before it starts the task. Setup performs explicit latest installs. This differs from the usual tech-stack wrapper rule because installation is this repo's purpose.
