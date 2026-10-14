# Verify an SR 4.1 installation

`read_only` mode. Do not modify, install, restore, or repair files.

```bash
python3 scripts/codex/verify_codex_pack.py
python3 scripts/codex/validate_release_docs.py --root . --json
python3 scripts/codex/audit_codex_pack.py --root . --json
python3 scripts/codex/sr_post_install_check.py --root . --json
```

Verify `4.1.0`, `AGENTS.md`, routes, `MCP_POLICY.yaml`, `task_state.yaml`, lots, passes, localized docs, and preservation. SR Contract 3.1.0, 3.0.0 contracts, and `audit_sr_task_contracts.py` remain legacy-readable. Report evidence, warnings, conflicts, and limits, then stop without repairing.
