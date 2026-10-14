# Définir les lots SR 4.1

Ne code pas. Lis le `AGENTS.md`, la demande concernée et l'éventuel `SR_LOTS.yaml`; consulte seulement les fichiers indispensables.

Distingue nouvelle capacité et réparation. `existing_requirement_repair` rouvre le lot ; `validated_requests` reste un champ de compatibilité. Propose le minimum de lots cohérents avec objectif, `Scope`, critères observables, dépendances, `Verification`, `Activation`, décisions humaines et conditions d'arrêt.

N'ajoute pas de gate documentaire autonome. Le cœur ne dépend d'aucun MCP ; toute capacité externe respecte `MCP_POLICY.yaml`. Utilise `task_state.yaml` seulement pour une continuité utile, puis valide le contrat.
