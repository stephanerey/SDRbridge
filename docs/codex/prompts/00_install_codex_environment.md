# Installer SR Method 4.1 dans un projet neuf

Ne code pas. Objectif : installer la version publiee `4.1.0`, verifier l'installation, puis stopper avant tout travail applicatif.

1. Lire le `AGENTS.md` le plus proche et inspecter la cible sans mutation.
2. Choisir explicitement `SR_PACK_SOURCE`; relever `version`, `release_status`, `source_commit` et l'etat Git. Refuser une source qui ne correspond pas a la release attendue.
3. Si un marqueur SR existe deja (`docs/codex/SR_PACK_VERSION.json`, `SR_METHOD.md` ou `SR_LOTS.yaml`), utiliser `05_upgrade_codex_environment.md`.
4. Sinon previsualiser :

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

Rapporter les creations, preservations et controles. Attendre l'autorisation exacte exigee par le projet, puis utiliser `--write`. Ne pas inventer de lot, passe, exigence ou capacite MCP.

Verifier ensuite :

```bash
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

La cible doit contenir un `AGENTS.md` court, `SR_LOTS.yaml`, `SR_PASSES.yaml` avec `passes: []`, `MCP_POLICY.yaml` en mode `core` et le template `task_state.yaml`. Aucun code, secret, migration, dependance ou deploiement applicatif ne doit changer.

Parcours : installation `00 -> 06`; installation existante `05 -> 06 -> 07`.
