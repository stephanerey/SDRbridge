# Changelog

This file explains what each SR Method release changes for developers and for existing installations.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The pack uses semantic versioning for public releases. `core/SR_PACK_VERSION.json` remains the machine-readable version source; this file is the human-readable release history.

## [Unreleased]

No change recorded yet.

## [4.1.0] - 2026-09-24

- Short `AGENTS.md` kernel with trigger-driven routes and immediate reconciliation during fresh installs and upgrades.
- Removal of the TDD workflow and of planning, terminal, diff-review and RepoMap cognitive skills; their useful mechanics stay in the harness.
- Three final boundaries only: Scope, Verification and Activation. No intentionally failing test or artificial rollback loop.
- Compact task state for new work while legacy SR and loop contracts remain readable.
- Explicit MCP policy with core-mode prohibition, deferred Nexus capabilities, allowlists, approvals, result budgets and bounded retries.
- Content-derived, source-version-agnostic convergence with per-file classification and safe removal of recognized obsolete managed artifacts.
- Separate context occupancy, uncached input, cached input/write, output and tool-result accounting.
- Full public, method, prompt, template and machine-metadata documentation alignment.
- All distributed agent prompts use the lean 4.1 boundaries, conditional MCP policy and compatibility-only legacy fields; prompt validation rejects the obsolete autonomous lot-design gate.
- Pack tests, fixtures and measurement helpers remain source-only instead of polluting every application repository.

## [4.0.0] - 2026-09-17

Existing SR Contract 3.1.0 / legacy 3.0.0 and Loop Contract 1.1 remain supported.

- Progressive context routing and canonical procedures; preserved authorization, evidence and completion guarantees.
- Content-based install/upgrade preview, custom-file conflict detection, transaction journal and guarded restoration.
- Explicit resume selection, compact diagnostics, read-only derived coverage, separate telemetry semantics.
- Fresh-install and version-agnostic upgrade documentation in five languages.
- Installation prompts validated in five languages, verification-only checks, and progressive post-upgrade realignment.
- No application rollout or changes to context stop thresholds.


## [3.7.0] - 2026-08-24

### Added

- SR Contract 3.1.0 with one persistent `validated_requests` entry per validated user intention.
- Separate `implementation_status` and `evidence_status`, typed expected/obtained evidence, requirement lineage, repair history, and explicit dispositions.
- Derived requirement decisions and Completion Gates, consolidated reopening, inherited open requirements, and guarded new-lot creation.
- Upgrade regressions for representative SR 2.2.0, 2.3.0, 2.3.5, 2.4.1, 3.0.0, and minimal unknown/partial layouts.
- Canonical release changelog and automated release-documentation validation.

### Changed

- `user_testing` is valid only when every required technical implementation is complete and only real E2E or human acceptance remains.
- Feedback about an existing requirement reopens the original lot by default and reloads its complete open checklist.
- Fresh installations and upgrades without product passes receive a valid `passes: []` registry instead of an invented example pass.
- The installer refuses fresh `--write` mode when SR markers already exist; upgrades preserve project-owned state and synchronize the managed AGENTS block.
- Public developer entry prompts and installation guides are maintained as a tested multilingual set.

### Migration and compatibility

- SR Contract 3.0.0 remains readable and is not mass-rewritten.
- Generic multi-lot legacy requirements receive a normalization warning; active or reopened scope must be reconstructed from actual sources.
- Unknown, partial, or locally adapted installations still require a file-by-file audit.
- Installer exit code `0` is insufficient: a red post-install check keeps the target in `repair`.

### Validation

- Requirement-traceability scenarios cover partial UI, pending authenticated E2E, existing-requirement feedback, genuinely new scope, contradictory contracts, and handoff continuity.
- Installation regressions verify fresh install and additive legacy upgrades while preserving lots, task memories, handoffs, and local project skills.

Source release: `v3.7.0`.

## [3.6.0] - 2026-08-13

### Added

- UI Verification Harness for significant UI/UX work.
- Project-level `ui_validation` configuration, Playwright route-by-viewport runner, UI Test Readiness Gate, UI Visual Evidence Gate, and machine-readable UI evidence in SR contracts.
- `aurora-ui-visual-qa` method skill.

### Migration and compatibility

- Fresh installations receive the harness automatically.
- Existing non-UI work remains compatible when `ui_validation` is absent, but significant UI lots cannot reach `done` without the required readiness and visual evidence.
- `playwright_auth_smoke.mjs` remains available as a compatibility wrapper.

Source release: `575f16f` (`v3.6.0`).

## [3.5.2] - 2026-08-08

### Fixed

- Historical task contracts created before the Lot Completion Gate cutoff now produce compatibility warnings instead of blocking every upgrade.
- SR upgrades no longer close, promote, or reclassify application lots or passes as an implicit side effect.

### Migration and compatibility

- An explicitly requested application-lot closure must run as a separate validated sub-phase with its own evidence.

Source release: `5ef43e3` (`v3.5.2`).

## [3.5.1] - 2026-08-08

### Changed

- Upgrade prompt `05` now treats every target repository independently and supports old, partial, unknown, and locally adapted SR installations.
- Upgrade flow explicitly requires diagnosis, classification, preservation, validation, additive mutation, verification, and state realignment.

Source release: `af37315` (`v3.5.1`).

## [3.5.0] - 2026-08-08

### Added

- Lot Design Evidence Gate.
- Scope-to-lots prompt `09_define_sr_lots_from_scope.md`.

### Changed

- Exploratory work may remain `proposed`, but executable lot states require candidate-file identification and actual code reading, or a justified `not_applicable` decision.

Source release: `2d58e50` (`v3.5.0`).

## [3.4.0] - 2026-08-08

### Added

- Pass Runtime Goal support for Codex CLI `/goal`.
- `build_pass_runtime_goal.py`, bounded goal-command length, Goal Length Gate, grouped E2E protection, and pass-end stop rules.
- Aurora SR Cockpit as optional read-only operator tooling; it is not installed into target projects.

### Changed

- A runtime goal is an execution helper only. `SR_PASSES.yaml`, `SR_LOTS.yaml`, and the task contracts remain the source of truth.

Source release: `0eda383` (`v3.4.0`).

## [3.3.0] - 2026-08-04

### Added

- Propagation Gate / Reference Integrity Gate for shared symbols and contracts.
- Pre-mutation consumer and risk declaration, human validation for non-local risk, and post-mutation reference checks.

### Migration and compatibility

- Historical contracts receive compatibility warnings when propagation metadata is absent; new affected work is strict.

Source release: `bc1512d`.

## [3.2.2] - 2026-07-22

### Added

- Lot Completion Gate with explicit coverage of every validated requirement.
- Contract and loop validation that rejects `done` when requirements are partial, blocked, or still awaiting required evidence.

Source release: `7ee4d4e` (`v3.2.2`).

## [3.2.1] - 2026-07-20

### Fixed

- Pass validation now recognizes ordered dependencies on lots placed in earlier proposed/planned passes while keeping executable passes strict.
- Added inter-pass dependency examples and regression tests.

Source release: `bdb6314` (`v3.2.1`).

## [3.2.0] - 2026-07-17

### Added

- SR Passes as a bounded orchestration layer above lots, with pass planning, ordering, preflight, stop conditions, and grouped E2E strategy.
- Pass contract, validator, templates, and multilingual pass-definition prompts.
- Framework-agnostic SR Agent Method with bounded product actions, stable internal representation, runtime contracts, typed outputs, message builders, tools/actions separation, routing, and validation.
- Backlog Mutation Gate, Global Impact Gate, and Lot Dependency Reconciliation.

### Migration and compatibility

- Existing `SR_LOTS.yaml` and task memories remain authoritative; upgrades add pass tooling without converting historical work automatically.

Source release: `3bd044e` (`v3.2.0`).

## [3.0.4] - 2026-06-30

### Added

- Machine-validatable SR and loop contracts for non-trivial work.
- Lot-contract validation, explicit gate reports, task-memory contract templates, and stronger completion checks.
- Backlog and execution rules for evidence, dependencies, risks, verification, and human validation.

### Changed

- A lot is no longer considered complete from implementation activity alone; contract validation and required evidence determine closure.

Source release: `28f50e6`.

## Earlier history

The public repository starts before 3.0.4, but earlier releases do not have enough stable release metadata to reconstruct a reliable version-by-version history. They are intentionally not invented here.
