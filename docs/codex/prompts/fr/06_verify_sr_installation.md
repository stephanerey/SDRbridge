# Verifier une installation SR 4.1

Mode `read_only`. Ne modifier, installer, restaurer ou corriger aucun fichier.

```bash
python3 scripts/codex/verify_codex_pack.py
python3 scripts/codex/validate_release_docs.py --root . --json
python3 scripts/codex/audit_codex_pack.py --root . --json
python3 scripts/codex/sr_post_install_check.py --root . --json
```

Verifier `4.1.0`, `AGENTS.md`, routes, `MCP_POLICY.yaml`, `task_state.yaml`, lots, passes, documentation et preservation. SR Contract 3.1.0, contrats 3.0.0 et `audit_sr_task_contracts.py` restent lisibles en legacy. Rapporter preuves, warnings, conflits et limites, puis stopper sans corriger.
