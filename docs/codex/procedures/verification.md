# Verification Gate

Prove the final result with the least expensive evidence that covers the risk:

1. inspection or static validation;
2. targeted lint, compile or existing check;
3. focused regression test when durable value justifies it;
4. affected build;
5. active runtime and health;
6. smoke or authenticated E2E;
7. human acceptance.

Do not require every layer. Do not create a failing test or red gate on purpose. An intermediate development failure is evidence to diagnose, not a rollback event. Report unexecuted proof honestly.
