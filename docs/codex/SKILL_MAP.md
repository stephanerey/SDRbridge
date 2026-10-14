# SKILL_MAP.md — {{PROJECT_NAME}}

Cette carte sert au routage, pas au chargement global. Lire une skill seulement quand son declencheur est present et limiter une tache a deux skills simultanees, sauf justification explicite.

## Skills methode par defaut

- `aurora-lot-runner` : roadmap, gros brief, reprise ou execution multi-lots.
- `aurora-diagnose` : anomalie a expliquer avant correction.
- `aurora-architecture-check` : DB, integration, orchestration, dependance ou refactor structurant.
- `aurora-ui-visual-qa` : modification UI/UX significative avec preuve visuelle.

## Skills facultatives

- `aurora-to-prd` : besoin produit reellement ambigu.
- `aurora-domain-skill-factory` : aucun savoir metier local pertinent n'existe.

La planification, la memoire de tache, la compression terminal, la revue finale, la maintenance RepoMap et la selection des tests sont des mecanismes du harness. SR 4.1 ne fournit pas de skill TDD et ne demande jamais de test volontairement rouge.

## Skills projet et runtime

Les skills `docs/codex/project-skills/**/SKILL.md` sont propres au projet et doivent etre declarees dans `PROJECT_PROFILE.yaml`. Ne charger que la skill metier correspondant a la tache. Les skills runtime embarquees dans l'application suivent `AI_AGENT_RUNTIME_METHOD.md` et ne sont pas des skills Codex.

## Connaissance

- `core` : RepoMap puis code reel cible ; aucun appel MCP.
- `nexus_kg` : appliquer `MCP_POLICY.yaml`, demander seulement la capacite utile, borner les resultats, puis verifier dans le code reel.
