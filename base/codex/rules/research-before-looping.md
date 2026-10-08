# Research Before Looping

When a fix attempt fails twice on the same issue, STOP and research the tool's documented limitations before trying a third time.

## Pattern

1. First attempt fails → adjust approach, try again
2. Second attempt fails with similar symptoms → **STOP**
3. Research: check official docs, known limitations, GitHub issues
4. Then decide: fix the approach, switch tools, or surface the limitation to the user

## Why

Guessing at workarounds for tool limitations wastes time. The answer is usually on the first page of the tool's docs. DuckDB concurrency, SQLite locking modes, API rate limits — these are documented constraints, not bugs to debug.

## Anti-pattern

```
Attempt 1: fails → "let me try X"
Attempt 2: fails → "let me try Y"
Attempt 3: fails → "let me try Z"
Attempt 4: fails → "let me try..."
```

## Correct pattern

```
Attempt 1: fails → adjust, retry
Attempt 2: fails → "let me try Y"
Attempt 3: fails → STOP → research official docs, best practices, GitHub issues, etc → distill to 2–3 viable options with trade-offs and present to user
```
