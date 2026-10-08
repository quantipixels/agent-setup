# Agent setup

Duplicate the team's base Claude Code and Codex setup on a Mac. Give an agent this repo link and ask it to follow this runbook. The step scripts do the file work; the agent handles the named pauses.

All tools, plugins and skills use the latest release. `last-good.lock` records a checked setup for rollback only. Setup never reads that lock to choose versions.

## Runbook

1. Clone `https://github.com/quantipixels/agent-setup.git` and enter the checkout. Read `base/` and this file. Use Python 3.11 or newer, Git and mise. If these are missing, pause before any brew or sudo command. Install them by hand:

   ```sh
   brew install mise python git
   mise trust
   ```

2. Run `mise run plan`. It prints the proposed file diff without applying it. Pause: let the person approve the diff. JSON and TOML merge recursively; repo keys win and host-added keys stay. Arrays use repo values. Machine-specific project trust, auth, caches and desktop settings are excluded from the base.
3. Pause on live-file conflicts. Read the live file and agree on the result before running apply with `--yes`. A backup goes to `~/.agent-setup/backups/<date>/` before each overwrite. Do not treat `--yes` as permission to remove anything.
4. Pause for logins. The person runs `! gh auth login` from Claude Code (or `gh auth login` in a terminal), `claude auth login`, and `codex login`. Do not collect or copy credentials. Public installs can run with `--no-login`.
5. After approval, run `mise run setup -- --yes`. To omit login prompts, run `mise run setup -- --no-login --yes`. Setup installs latest tools, updates marketplaces, installs plugins and skills, renders the agent roles, applies files, and runs doctor. A failed install is a failed setup.
6. Run `mise run doctor`. A full pass checks the configured files and installed dependencies. Keep its profile with the result. An offline structural pass does not prove tool installs, login or live agent operation.
7. Pause before removals. `mise run cleanup` shows its proposal. Use `--approve-removals` only after approval. Never delete host-owned plugins or skills to match the base.

Start a new Claude Code and Codex session after setup. Confirm that the status line, hooks, skills and agent roles load. These live checks need the person's login and are separate from scratch CI.

## Toolkit

| Language | Tool | Why |
| --- | --- | --- |
| Always | rg, fd, jq, ast-grep, lefthook, gitleaks, mise | Search, inspect JSON, match code, run checks, find secrets, manage tools |
| TS | typescript-lsp, biome | Code intelligence, format and lint |
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
