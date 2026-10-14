# Installer SR Method 4.1 dans un projet neuf

Ne code pas. Installer la version publiee `4.1.0`, la verifier, puis stopper avant tout travail applicatif. Lire le `AGENTS.md` le plus proche, choisir `SR_PACK_SOURCE` explicitement et relever `release_status`, `source_commit` et l'etat Git. Refuser une source qui ne correspond pas a la release attendue. Si un marqueur SR existe, utiliser `05_upgrade_codex_environment.md`.

Previsualiser, rapporter creations et preservations, attendre l'autorisation exacte, puis utiliser `--write` :

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

La cible doit contenir `SR_LOTS.yaml`, `SR_PASSES.yaml` avec `passes: []`, `MCP_POLICY.yaml` en mode `core` et `task_state.yaml`. N'inventer aucun lot, passe, besoin ou appel MCP. Ne modifier aucun code, secret, migration, dependance ou deploiement applicatif. Parcours : `00 -> 06` ou `05 -> 06 -> 07`.
