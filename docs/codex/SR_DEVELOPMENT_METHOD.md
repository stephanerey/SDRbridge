# SR Development Method 4.1

Use for changes to source, configuration, tests or build assets.

1. State objective, assumptions, smallest sufficient change and final verification.
2. Load only routes triggered by the task.
3. Inspect the real files and affected consumers.
4. Implement surgically without unrelated refactor or dependency change.
5. Verify the final result using `procedures/verification.md`.
6. If activation was requested, apply `procedures/build.md` and distinguish every proof layer.

No TDD workflow is required. Existing tests may be used or a durable regression check may be added after the behavior is understood.
