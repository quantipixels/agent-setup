#!/bin/sh
# PreToolUse(Bash): remove Claude attribution lines from git commit and gh commands.
exec python3 "$(dirname "$0")/strip-claude-attribution.py"
