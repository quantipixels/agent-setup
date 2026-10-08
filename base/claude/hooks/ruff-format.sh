#!/bin/sh
# Format edited Python files only when the project configures Ruff.
set -eu
file=$(jq -r '.tool_response.filePath // .tool_input.file_path // empty')
case "$file" in *.py) ;; *) exit 0 ;; esac
[ -f "$file" ] || exit 0
dir=$(dirname "$file")
while [ "$dir" != / ] && [ "$dir" != . ]; do
    if [ -f "$dir/ruff.toml" ] || [ -f "$dir/.ruff.toml" ] || grep -qs '^\[tool\.ruff' "$dir/pyproject.toml"; then
        ruff check --fix --quiet --exit-zero "$file"
        ruff format --quiet "$file"
        exit 0
    fi
    dir=$(dirname "$dir")
done
