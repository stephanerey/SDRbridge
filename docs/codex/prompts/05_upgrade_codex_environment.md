# Mettre a jour une installation SR vers 4.1

Ne code pas. Objectif : faire converger une installation SR ancienne, partielle, inconnue ou adaptee vers la version publiee `4.1.0`, sans ecraser le projet.

## Diagnostic sans mutation

1. Lire le `AGENTS.md` le plus proche, les marqueurs SR, `CURRENT_STATE`, lots, passes et memoires actives.
2. Choisir explicitement `SR_PACK_SOURCE`; relever `release_status`, `source_commit` et l'etat Git. Refuser une source qui ne correspond pas a la release attendue.
3. Previsualiser :

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
```

La version precedente est une information de provenance, jamais une branche d'algorithme. Classer le contenu reel : `absent`, `managed`, `locally_modified`, `unmanaged`, `obsolete`, `conflict` ou `already_aligned`.

## Regles de convergence

- Remplacer le contenu gere reconnu et reconcilier le bloc SR de `AGENTS.md` en un noyau court.
- Preserver code, secrets, configuration, dependances, lots, passes, exigences ouvertes, historiques, skills projet et regles locales.
- Supprimer un artefact obsolete seulement si son empreinte est reconnue comme geree; sinon le preserver et le signaler.
- Reconcilier `PROJECT_PROFILE.yaml` par capacite, sans reecriture globale.
- Ajouter `MCP_POLICY.yaml` et `task_state.yaml`; garder les anciens contrats lisibles sans migration de masse.
- Ne fermer, promouvoir ou requalifier aucun lot. Ne lancer aucun build, deploiement, migration, appel MCP ou action produit.

Rapporter le plan, les conflits et les preservations, puis attendre l'autorisation exacte exigee par le projet. Apres validation :

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --upgrade
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

Un code retour d'installation ne suffit pas : le post-check doit verifier `4.1.0`, les routes, la documentation, le catalogue de skills, l'absence de TDD obligatoire et la preservation du projet. En cas de conflit, stopper avec le diagnostic; ne pas provoquer un rollback de developpement.

Ensuite utiliser `06_verify_sr_installation.md`, puis `07_realign_sr_state_after_upgrade.md` uniquement si l'etat du projet doit reellement etre reconcilie.
