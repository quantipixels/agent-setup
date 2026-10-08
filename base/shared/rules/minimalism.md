# Code Minimalism

Do only what was asked. The right amount of code is the minimum that solves the current task.

## Scope Discipline

- Only modify files and functions directly required by the task.
- A bug fix does not need surrounding code cleaned up.
- A simple feature does not need extra configurability.
- Do not add docstrings, comments, or type annotations to code you did not change.
- Only add comments where the logic is not self-evident.
- Keep diffs minimal and reviewable — a 1-function change should not touch 5 files.

## No Speculative Code

- Do not add error handling, fallbacks, or validation for scenarios that cannot happen.
- Trust internal code and framework guarantees.
- Only validate at system boundaries: user input, external APIs, deserialization.
- Do not use feature flags or backwards-compatibility shims when you can just change the code.

## No Premature Abstraction

- Do not create helpers, utilities, or abstractions for one-time operations.
- Do not design for hypothetical future requirements.
- Three similar lines of code is better than a premature abstraction.
- Do not add new dependencies when existing ones cover the need.

## Clean Removal

- Do not rename unused variables to _vars as a compatibility hack.
- Do not re-export removed types or add `// removed` comments for deleted code.
- If something is unused, delete it completely.

## Pattern Conformity

- Before introducing a new pattern, check if the codebase already solves this differently.
- Follow existing patterns unless they are demonstrably broken.
- When in doubt, match the surrounding code style, not your preference.
