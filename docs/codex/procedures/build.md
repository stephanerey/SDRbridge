# Build and activation

Use only after an explicit build, rebuild, restart or deployment request.

1. Identify the exact repository, environment, affected services, official command, active artifact and rollback candidate.
2. Record Git state and capacity without cleaning unrelated work or shared resources.
3. Run proportionate preparatory checks, build only affected services, then activate only those services.
4. Verify in layers: source, built artifact, active runtime, health, bounded logs, smoke, authenticated E2E when safe, then human acceptance when required.
5. Roll back only when the activated runtime is genuinely degraded and restoration is safe.
6. Remove only exact superseded project artifacts after success; never run a global prune.
