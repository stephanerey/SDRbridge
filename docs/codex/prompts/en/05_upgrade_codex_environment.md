# Upgrade an SR installation to 4.1

Do not code. Converge an old, partial, unknown, or adapted installation to released version `4.1.0` without overwriting the project.

Read the nearest `AGENTS.md`, SR markers, current state, lots, passes, and active memory. Select `SR_PACK_SOURCE` explicitly; record `release_status`, `source_commit`, and Git state. Preview:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

The previous version is provenance only. Classify content as `absent`, `managed`, `locally_modified`, `unmanaged`, `obsolete`, `conflict`, or `already_aligned`. Converge recognized managed content, shorten the SR block in `AGENTS.md`, and preserve application code, secrets, dependencies, product state, history, and local skills. Delete obsolete artifacts only when fingerprints are recognized. Reconcile the profile by capability; add `MCP_POLICY.yaml` and `task_state.yaml`; keep old contracts readable.

Report plan, conflicts, and preservation, then wait for exact authority. After validation:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --upgrade
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

Close no lot and run no build, deployment, migration, or MCP call. The post-check must prove `4.1.0`, routes, docs, skills, and preservation. Legacy labels `managed_update`, `already_current`, and `reconciliation_required` remain readable; no branch depends on a version such as `2.2.0`. Next use `06_verify_sr_installation.md`, then `07_realign_sr_state_after_upgrade.md` only when needed.
