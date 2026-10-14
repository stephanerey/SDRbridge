# Définir les passes SR 4.1

Ne code pas. Lis le `AGENTS.md` applicable, `SR_LOTS.yaml` et l'éventuel `SR_PASSES.yaml`; n'ouvre le produit ou `task_state.yaml` qu'en cas de besoin réel.

Regroupe les lots `repair`, `reopened` ou `validated` dans le minimum de passes cohérentes. Pour chacune : objectif, `Scope`, dépendances, `Verification` finale, `Activation` séparée, décisions humaines et conditions d'arrêt.

Ne crée aucune gate documentaire autonome. Les champs historiques restent de simples compatibilités. Le cœur ne dépend d'aucun MCP ; toute capacité externe respecte `MCP_POLICY.yaml`.

Propose le diff, respecte la validation humaine applicable, puis valide le contrat.
