# Définir les skills métier nécessaires

Ne code pas et ne génère pas encore les skills.

Utilise ce prompt seulement lorsqu'un manque métier confirmé ne peut pas être couvert par les instructions ou skills existants. Lis le `AGENTS.md` applicable, la demande validée et le minimum de sources métier nécessaires.

Propose le plus petit ensemble de skills Codex locales au projet, sous `docs/codex/project-skills/`. Pour chaque skill : déclencheur précis, responsabilité unique, sources de vérité, limites, sorties attendues et chevauchements évités. Sépare explicitement ces skills d'assistance des agents `runtime` de l'application.

N'invente aucune règle métier. Ne rends aucun MCP obligatoire ; toute capacité externe doit respecter `docs/codex/MCP_POLICY.yaml`.

Rends une carte concise des skills proposées, des risques, des décisions humaines et des sources manquantes, puis attends la validation avant génération.
