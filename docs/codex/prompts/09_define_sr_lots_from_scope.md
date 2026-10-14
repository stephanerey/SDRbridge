# Définir les lots SR 4.1

Ne code pas l'application.

Lis le `AGENTS.md` applicable, la demande ou l'inbox concernée et, s'il existe, `docs/codex/SR_LOTS.yaml`. Ouvre seulement les fichiers produit indispensables pour confirmer le périmètre.

Distingue une nouvelle capacité d'une réparation d'exigence existante. `existing_requirement_repair` rouvre le lot concerné ; `validated_requests` reste un champ de compatibilité lorsqu'il existe déjà, pas une gate supplémentaire.

Propose le minimum de lots cohérents. Pour chaque lot, indique :

- objectif et `Scope` autorisé/exclu ;
- critères d'acceptation observables ;
- dépendances utiles ;
- `Verification` finale proportionnée ;
- `Activation` éventuelle, séparée de l'implémentation ;
- décisions humaines et conditions d'arrêt.

N'ajoute aucune gate documentaire autonome. Si un ancien schéma requiert `design_evidence`, renseigne-le à partir des sources réellement consultées comme simple compatibilité. Le cœur SR ne dépend d'aucun MCP ; toute capacité externe doit être explicitement autorisée dans `docs/codex/MCP_POLICY.yaml`.

Présente le changement proposé pour `SR_LOTS.yaml`. Respecte toute gate humaine existante avant écriture. N'utilise `task_state.yaml` que pour la continuité utile, puis valide le contrat avec l'outil du dépôt.
