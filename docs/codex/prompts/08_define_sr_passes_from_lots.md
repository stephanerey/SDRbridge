# Définir les passes SR 4.1

Ne code pas l'application.

Lis le `AGENTS.md` applicable, `docs/codex/SR_LOTS.yaml` et, s'il existe, `docs/codex/SR_PASSES.yaml`. N'ouvre `docs/CURRENT_STATE.md`, `task_state.yaml` ou les fichiers du produit que lorsqu'ils sont nécessaires pour lever une ambiguïté.

Regroupe les lots `repair`, `reopened` ou `validated` dans le minimum de passes cohérentes. Une passe doit porter un résultat vérifiable, pas une micro-étape.

Pour chaque passe, propose :

- l'objectif et le `Scope` autorisé ;
- les dépendances et l'ordre utile ;
- une `Verification` finale proportionnée ;
- les éventuelles actions d'`Activation`, séparées de la preuve source ;
- les décisions humaines et conditions d'arrêt réelles.

Ne crée ni gate documentaire autonome, ni statut sans preuve, ni appel MCP dans le cœur de la méthode. Une capacité MCP n'est permise que par `docs/codex/MCP_POLICY.yaml`. Conserve `design_evidence` ou `validated_request_id` uniquement si le schéma historique les exige, comme champs de compatibilité et non comme nouvelles gates.

Présente d'abord le diff proposé pour `SR_PASSES.yaml`. Si le projet impose une validation stricte, attends-la avant d'écrire. Mets à jour `task_state.yaml` seulement si la continuité de session le justifie, puis exécute le validateur de contrats disponible.
