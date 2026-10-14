# Mettre a jour une installation SR vers 4.1

Ne code pas. Faire converger une installation ancienne, partielle, inconnue ou adaptee vers la version publiee `4.1.0`, sans ecraser le projet.

Lire le `AGENTS.md` le plus proche, les marqueurs SR, l'etat, les lots, passes et memoires. Choisir explicitement `SR_PACK_SOURCE`; relever `release_status`, `source_commit` et l'etat Git. Previsualiser :

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

La version precedente est seulement une provenance. Classer le contenu reel : `absent`, `managed`, `locally_modified`, `unmanaged`, `obsolete`, `conflict` ou `already_aligned`. Converger le contenu gere, reduire le bloc SR de `AGENTS.md`, preserver code, secrets, dependances, etat produit et historiques. Supprimer un obsolete seulement si son empreinte est reconnue; reconcilier le profil par capacite; ajouter `MCP_POLICY.yaml` et `task_state.yaml`; garder les anciens contrats lisibles.

Rapporter plan, conflits et preservations, puis attendre l'autorisation exacte. Apres validation :

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --upgrade
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

Ne fermer aucun lot et ne lancer aucun build, deploiement, migration ou appel MCP. Le post-check doit prouver `4.1.0`, routes, documentation, skills et preservation. Les libelles legacy `managed_update`, `already_current` et `reconciliation_required` restent lisibles; aucune branche ne depend d'une version telle que `2.2.0`. Suite : `06_verify_sr_installation.md`, puis `07_realign_sr_state_after_upgrade.md` si necessaire.
