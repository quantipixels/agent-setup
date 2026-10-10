# Instruction text belongs to qp-skills

Agent-setup and qp-skills both wrote personal instructions, so two owners overwrote each other and `apply` broke on the Codex symlink. Agent-setup now seeds `~/.agents/AGENTS.md` once, links Codex to it, and starts the Claude file with its import; qp-skills’ `asami` owns the text and `asoju` owns the model set. This keeps one source of personal defaults while agent-setup maintains the machine and host configuration.
