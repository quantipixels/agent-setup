# Test Quality Standards

These rules govern how tests are written, regardless of language or framework.

## Naming

Test names must describe **observable behavior**, not implementation.
Bad: `testSave`, `should call findById`. Good: `should return 404 when user not found`.
If the name needs "and", split into two tests.

## Assertion Density

One assertion *concept* per test. Multiple asserts verifying the same outcome are fine.
Two separate behaviors in one test → split.

## Coverage Requirement

Every behavior must have at minimum:
- One happy path test
- One failure or boundary path test

A behavior with only a happy path test is not considered covered.
For what qualifies as a behavior worth testing, see `unnecessary-tests.md`.

## Edge Cases to Always Test

- Null or empty inputs on public methods
- Lookups for records that do not exist
- Permission boundaries (authorized vs unauthorized)
- Duplicate creation (idempotency or conflict)

## No Logic in Tests

Test code must be unconditional and linear. Forbidden in test bodies:
- `if`/`else` — split into two tests
- Loops — use parameterized tests
- `try`/`catch` — use the framework's assertion for expected exceptions
- String concatenation to build expected values

Helper logic belongs in setup methods or factory functions, not inline.

## Complexity and Tests

High complexity = a design problem, not a test problem. See `cyclomatic-complexity.md` for thresholds.

## Post-implementation Cleanup

Tests written during TDD to drive scaffold or config code are subject to audit per `unnecessary-tests.md`. TDD governs the implementation phase; the test quality audit governs the finished product.
