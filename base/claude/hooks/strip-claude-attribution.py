import json
import re
import sys

d = json.load(sys.stdin)
cmd = d.get("tool_input", {}).get("command", "")
if not re.search(r"\bgit\b.*\b(commit|tag)\b|\bgh\b\s+(pr|issue|release|api)\b", cmd):
    sys.exit(0)
pats = [
    r"^[ \t]*Co-Authored-By:[^\n\"']*(Claude|Anthropic)[^\n\"']*\n?",
    r"^[ \t]*(🤖[ \t]*)?Generated with[ \t]+\[?Claude Code\]?[^\n\"']*\n?",
]
new = cmd
for p in pats:
    new = re.sub(p, "", new, flags=re.M | re.I)
if new != cmd:
    ti = dict(d["tool_input"], command=new)
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": ti}}
        )
    )
