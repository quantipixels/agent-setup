# Instruction text belongs to the workflow plugin

Agent-setup and the workflow plugin both wrote personal instructions, so two owners overwrote each other and `apply` broke on the Codex symlink. Agent-setup now seeds the user-owned `ofin` skill (`~/.agents/skills/ofin/SKILL.md`) once, links Codex to it, and starts the Claude file with its import. The workflow plugin owns the instruction text and model set. This keeps one source of personal defaults while agent-setup maintains the machine and host configuration.
