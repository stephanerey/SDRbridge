# Verifier une installation SR 4.1

Mode `read_only`. Ne modifier, installer, restaurer ou corriger aucun fichier.

```bash
python3 scripts/codex/verify_codex_pack.py
python3 scripts/codex/validate_release_docs.py --root . --json
python3 scripts/codex/audit_codex_pack.py --root . --json
python3 scripts/codex/sr_post_install_check.py --root . --json
```

Verifier la version `4.1.0`, le noyau `AGENTS.md`, `SR_ROUTES.json`, `MCP_POLICY.yaml`, `task_state.yaml`, `SR_LOTS.yaml`, `SR_PASSES.yaml`, la documentation localisee et la preservation des donnees projet. Les anciens SR Contract 3.1.0, contrats 3.0.0 et `audit_sr_task_contracts.py` restent lisibles mais ne sont pas obligatoires pour une nouvelle tache compacte.

Rapporter les preuves, warnings legacy, conflits et limites. Stopper sans corriger; toute reparation exige un perimetre distinct valide.
