---
title: Hook needs its tool
category: integrations
tags: [hooks, codex, shellcheck, setup]
problem_type: bug
date: 2026-10-10
---

## Context

The [Codex shellcheck hook](../../../../base/codex/hooks/shellcheck-validate.mjs) checks Bash commands before they run and fails closed when validation cannot run.

## What went wrong or was non-obvious

A machine without `shellcheck` had every Bash command blocked with no hint about the missing tool. Installing the hook did not ensure that its executable dependency existed.

## Guidance

Declare executable dependencies in each [hook row's `requires:` list](../../../../base/hooks.yaml). [Setup and apply](../../../../steps/engine.py) install missing requirements through the toolkit's mise path, then enable the hook only when its programs are on PATH. If installation fails or is skipped offline, skip the hook and report the reason and install command. Plan and dry run report missing requirements without installing anything; doctor and check-tools flag a missing requirement of an installed hook. The shellcheck hook also names the missing tool and its install command when it must deny a command.

## Evidence

[PR #5](https://github.com/quantipixels/agent-setup/pull/5) introduced hook requirements. The [regressions](../../../../tests/test_hook_tools.py) cover missing-tool denial, successful installation before enablement, failed and offline installs, dry runs, installed-hook diagnostics, and actual shellcheck warnings. Run `mise run check` for ShellCheck, gitleaks, and the test suite.
