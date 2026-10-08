# Unnecessary Tests

Prefer high-value tests. Do not add tests just because code was added or changed.

This rule overrides blanket expectations like "write tests for all new behaviors" when the added behavior is low-risk, obvious, or implementation-detail heavy.

## Test Only What Matters

Add tests when they protect:

- Business logic
- User-visible behavior
- Critical paths
- Bug regressions
- Data contracts and persistence boundaries
- Failure handling and edge cases with real risk
- Integration points that are easy to break silently

## Do Not Add Tests For

Do not add tests for low-value behavior such as:

- Existence checks (`is defined`, `returns an array`, `renders`)
- Router or config scaffolding that only restates static setup
- Simple getters/setters or pass-through wrappers
- Framework behavior already guaranteed by the library
- Test helpers, mock adapters, or fake implementations unless they contain real logic
- Internal implementation details that can change without changing behavior
- Duplicated coverage of the same behavior at multiple layers without additional risk reduction
- Trivial CRUD smoke tests when meaningful integration coverage already exists
- Snapshot-style assertions with little behavioral signal

## Decision Rule

Before adding a test, ask:

1. What real bug would this test catch?
2. Would a user, operator, or maintainer care if this broke?
3. Is this the cheapest layer that can verify the behavior?
4. Is this behavior already covered elsewhere with enough signal?

If those answers are weak, skip the test.

## Preferred Test Targets

Bias toward a small number of tests that validate:

- End-to-end behavior of a feature
- Core domain transformations
- Persistence and event ordering
- Contract boundaries
- Previously broken scenarios
- Branches with meaningful failure modes

Prefer one strong test over several shallow ones.

## Red Flags

A test is probably unnecessary if it mainly proves that:

- a value exists
- a mock was called
- a route was registered
- a config key is present
- a fake adapter yields something
- a function returns the same shape as its input
- a library still works as documented

## When Removing Tests

It is acceptable to delete or consolidate tests when they are:

- Redundant
- Purely structural
- Coupled to implementation details
- Slower than their value justifies
- Lower-signal duplicates of stronger coverage elsewhere

When trimming tests, preserve coverage for business logic, regressions, and critical flows.

## Default

When unsure, test the business outcome or regression path, not the implementation detail.
