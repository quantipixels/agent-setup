# Incremental Verification

Verify each change works before moving to the next.

## Build and Test Cadence

- After modifying a file, check it compiles (if applicable) before modifying the next.
- After completing a logical unit of work, run the relevant tests.
- Do not batch all changes across 5+ files then test once at the end.

## Regression Awareness

- Before modifying existing code, identify its tests.
- Run those tests before and after your change.
- If tests fail after your change, fix the implementation — do not disable or weaken the tests.

## Verify Imports and References

- After adding an import, verify the symbol exists at that path.
- After moving or renaming, verify all references update.
- After deleting, search for remaining references before considering the task done.
