# Point d'entrée Codex

## Lire en premier

**Pour lancer la réalisation : [prompt prêt à transmettre](handoff/START_IMPLEMENTATION.md).** Pack v0.3 : le PRD est complété par [S6, référence d'exécution](specs/06_IMPLEMENTATION_BASELINE.md), qui tranche les propositions techniques v0.2. La préparation n'a pas démarré les fonctionnalités produit.

1. `AGENTS.md` à la racine.
2. [CURRENT_STATE](work/CURRENT_STATE.md), pour connaître les faits et la prochaine action.
3. [BACKLOG](work/BACKLOG.md), uniquement le lot demandé et ses dépendances.
4. Les décisions mentionnées par le lot dans [DECISIONS](product/DECISIONS.md), puis les spécifications utiles ci-dessous.

Le [PRD](product/PRD.md) est une carte des exigences ; les comportements détaillés sont répartis par sujet. Ne pas charger tous les documents à chaque tâche.

| Travail demandé | Documents à charger |
|---|---|
| Cadrage ou changement de périmètre | PRD + DECISIONS |
| Reprise de la base de Philippe | [État de référence](reference/UPSTREAM_BASELINE.md) + lot SDB-BASE-001 |
| Acquisition, RF ou GUI | [Comportements et écrans](specs/01_BEHAVIOR_UI.md) + [contrats du cœur](specs/02_CORE_CONTRACTS.md) si interface affectée |
| Ring, sessions et cycle de vie | Contrats du cœur + état de référence |
| Resampling et formats IQ | [DSP](specs/03_DSP.md) + contrats du cœur |
| Contrôle réseau ou UDP | [Réseau](specs/04_NETWORK.md) + contrats du cœur |
| Presets, reprise, enregistrement, headless | [Exploitation](specs/05_OPERATIONS.md) |
| Vérification et recette | Cas concernés de [ACCEPTANCE](verification/ACCEPTANCE.md) |
| Installation ou mise à jour de méthode | [SR 4.1](tooling/SR41_INTEGRATION.md) |
| Nexus | [Évaluation MCP](tooling/NEXUS_MCP_EVALUATION.md) |

## Autorité des documents

Une instruction utilisateur récente prévaut sur les documents. Avec le prompt de lancement, S6 prévaut sur les propositions techniques v0.2 ; PRD et décisions acquises cadrent le produit, les exemples n'ajoutent aucune exigence. Lire S6 une fois au lancement puis seulement les sections concernées.

En cas de contradiction, signaler précisément les deux règles avant une modification qui dépend de leur résolution. Ne pas importer implicitement une ancienne règle SR 3.6 depuis l'archive.

## Exécuter un lot après son autorisation

Confirmer brièvement l'objectif, lire le code concerné, appliquer les actions du lot, exécuter les cas de preuve applicables et consigner le résultat. L'autorisation d'un lot couvre ses actions délimitées ; ne pas redemander une validation pour chaque petite étape. Si une décision produit manquante affecte le résultat, arrêter seulement cette partie et poursuivre les actions indépendantes.

Les champs et protocoles décrits ici restent de nouveaux contrats à implémenter ; la structure exacte des modules doit préserver les conventions du code importé. Ne pas produire une architecture parallèle seulement pour reproduire les noms conceptuels des documents.

Registres officiels : `docs/codex/SR_LOTS.yaml` et `SR_PASSES.yaml`. La préparation est faite ; les passes de code restent proposées jusqu'au prompt utilisateur de lancement. Preuves initiales : [rapport de préparation](reference/PREPARATION_REPORT.md). Interface Qt : [DESIGN](product/DESIGN.md).
