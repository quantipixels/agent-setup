# Commit Protocol

Use git trailers to preserve decision context in every commit message.

## Format

**Subject line:** Conventional Commits (`<type>(<scope>): <description>`)

**Body:** Explain *why* — what problem does this solve, what constraint shaped the decision.

**Trailers** (include when applicable — skip for trivial commits like typos or formatting):
- `Constraint:` active constraint that shaped this decision
- `Rejected:` alternative considered | reason for rejection
- `Directive:` warning or instruction for future modifiers
- `Confidence:` high | medium | low
- `Scope-risk:` narrow | moderate | broad
- `Not-tested:` edge case or scenario not covered by tests

## Rules

- Stage only files relevant to the task — never `git add -A` or `.`
- No co-author attribution
- Present the plan and wait for explicit user approval before committing
- Simple commits (1–4 files, straightforward): single subject line. Complex commits (5+ files, refactors, migrations): include body with reasoning

## Example

```
fix(auth): prevent silent session drops during long-running ops

Auth service returns inconsistent status codes on token expiry,
so the interceptor catches all 4xx and triggers inline refresh.

Constraint: Auth service does not support token introspection
Rejected: Extend token TTL to 24h | security policy violation
Confidence: high
Scope-risk: narrow
Directive: Error handling is intentionally broad (all 4xx) — do not narrow without verifying upstream behavior
```
