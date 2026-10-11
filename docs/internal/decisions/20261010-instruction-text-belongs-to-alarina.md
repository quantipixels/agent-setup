# Instruction text belongs to Alárinà

Agent-setup and the personal-defaults plugin both wrote personal instructions, so two owners overwrote each other and `apply` broke on the Codex symlink. Agent-setup now seeds the user-owned `ofin` skill (`~/.agents/skills/ofin/SKILL.md`) once, links Codex to it, and starts the Claude file with its import. Alárinà’s `asami` owns the text and `asoju` owns the model set; `qp-skills` is retired. This keeps one source of personal defaults while agent-setup maintains the machine and host configuration.
