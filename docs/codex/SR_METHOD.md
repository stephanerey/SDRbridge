# SR Method 4.1

SR is a lightweight execution harness for reliable software work. Its purpose is to preserve scope, evidence and continuity without flooding model context.

## Operating model

1. `AGENTS.md` keeps permanent invariants and routes only.
2. `SR_ROUTES.json` selects the smallest applicable procedure.
3. Specialized skills are loaded only for an exact workflow.
4. Real source and proportionate evidence decide the result.
5. One compact task state preserves continuity when useful.

## Three gates

- **Scope Gate** before a non-trivial mutation: authority, scope, protected state and smallest sufficient approach.
- **Verification Gate** after implementation: least expensive evidence covering the actual risk.
- **Activation Gate** only for build, restart or deployment: active artifact, runtime proof and verified rollback.

Do not create failing tests or red gates on purpose. Rollback is for a genuinely degraded activated runtime, not for normal source iteration.

## Knowledge modes

- `core`: focused search, real source and optional RepoMap. No MCP schema or call.
- `nexus_kg`: the same sources plus capabilities explicitly resolved and allowed by `MCP_POLICY.yaml`.

## Continuity

Simple work creates no SR state. A non-trivial task may use one `task_state.yaml`. Multi-lot work may also use inbox, lots and passes. Legacy contracts stay readable.

## Completion

Report the result, changed files, executed proof, unverified layers and remaining human acceptance. Do not recite unused gates or repeat raw logs.
