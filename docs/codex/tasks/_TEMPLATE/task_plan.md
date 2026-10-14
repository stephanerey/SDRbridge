# task_plan.md

## Objectif verifiable
...

## Bootstrap SR
- SR_BOOTSTRAP lu : oui/non
- Reprise apres compact/resume/handoff : oui/non
- Derniere memoire de tache consultee : oui/non

## Hypotheses
- ...

## Type de tache
- [ ] UI
- [ ] Backend
- [ ] DB/migration
- [ ] Integration
- [ ] Securite
- [ ] Documentation
- [ ] Architecture
- [ ] Bugfix
- [ ] Domaine metier

## Skills utilisees
- ...

## Skills metier Codex
- Skill metier pertinente selectionnee : oui/non/non applicable
- Si non, skill a proposer :
- Sources domaine lues :

## Agents IA runtime
- Tache touche un agent IA/runtime/LLM : oui/non
- AI_AGENT_RUNTIME_METHOD lu : oui/non/non applicable
- Action produit bornee definie : oui/non/non applicable
- Runtime shape declare : oui/non/non applicable
- Representation interne stable definie : oui/non/non applicable
- User message builder identifie : oui/non/non applicable
- Tools/actions distingues : oui/non/non applicable
- Routing/fallback defini si ambigu : oui/non/non applicable
- Skills runtime concernees :
- Validation humaine requise : oui/non/non applicable

## Sources lues
- [ ] AGENTS.md
- [ ] DESIGN.md
- [ ] docs/CURRENT_STATE.md
- [ ] docs/codex/PROJECT_PROFILE.yaml
- [ ] docs/codex/SR_BOOTSTRAP.md
- [ ] docs/codex/SKILL_MAP.md
- [ ] docs/codex/AI_AGENT_RUNTIME_METHOD.md
- [ ] docs/codex/DOMAIN_EXPERTISE_BOOTSTRAP.md
- [ ] docs/codex/CODEBASE_MAP.md
- [ ] docs/codex/CODEBASE_MAP.generated.md

## RepoMap
- CODEBASE_MAP.md lu : oui/non
- generated consulte : oui/non
- fichiers candidats :
- fichiers verifies :
- RepoMap a mettre a jour : oui/non

## Lot Design Evidence Gate
- Requis pour statut executable : oui/non
- Statut : pending/pass/fail/not_applicable
- Lecture code requise : oui/non
- Fichiers candidats :
- Fichiers confirmes lus :
- Symboles/routes/services/schemas/verifications :
- Tests/logs consultes :
- Hypotheses restantes :
- Questions bloquantes :
- Raison si not_applicable :
- Statut maximal si gate non passe : proposed

## Knowledge mode
- Mode : `core` / `nexus_kg`
- Nexus KG consulte : oui/non/non disponible
- Fraicheur KG verifiee : oui/non/non disponible
- Context pack Nexus requis : oui/non
- KG a mettre a jour en cloture : oui/non/non applicable

## Lot naming
- Lot ID :
- Conforme `<PROJECT_KEY>-<AREA>-<SEQ>` : oui/non/legacy
- Alias legacy :

## Perimetre valide et Lot Completion Gate
- Lot/passe valide explicitement : oui/non
- Source de validation :
- Perimetre decrit juste avant validation :
- Reduction/decoupage necessaire avant mutation : oui/non
- Si oui, nouvelle validation utilisateur obtenue : oui/non/non applicable

| Exigence validee | Preuve minimale prevue | Risque de couverture | Statut attendu |
|---|---|---|---|
| ... | fichier/test/log/capture/E2E | faible/moyen/fort | fait/requires_e2e |

- Exigence UI/UX explicite : oui/non
- Verification visuelle ou E2E prevue :

## Propagation Gate
- Requis : oui/non
- Declencheur : symbole / signature / type / schema / endpoint / champ DB / config / import-export / composant / agent runtime / non applicable
- Niveau de risque : low / medium / high / critical / not_applicable
- Changement prevu :
- Ancien contrat :
- Nouveau contrat :
- Consommateurs detectes avant mutation :
- Surfaces a risque :
- Strategie : full_propagation / compatibility_shim / two_step_migration / not_required
- Recherches de references prevues :
- Verifications consommateurs prevues :
- Validation humaine requise : oui/non
- Validation humaine recue : oui/non/non applicable

## Pass Runtime Goal
- Requis : oui/non
- Passe :
- Statut de passe :
- Fichier prevu : `docs/codex/tasks/YYYY-MM-DD_slug/pass_runtime_goal.md`
- Generation prevue : `python3 scripts/codex/build_pass_runtime_goal.py --pass-id <PASS_ID> --output <fichier>`
- `max_goal_command_chars` : 1000
- `hard_limit` : 4000
- Goal Length Gate prevu : oui/non
- E2E groupe protege : oui/non/non applicable
- Enchainement de passe suivante interdit sans validation : oui/non/non applicable

## Context budget
- `context_budget_report.py --root . --compact` execute : oui/non/non disponible
- Statut contexte hybride : green/yellow/orange/red/unknown/stale/ambiguous
- Selection session fiable : oui/non
- Cached/uncached consultes : oui/non
- Signaux hybrides : contexte / uncached / cache_ratio / tours / lots
- `NEXT_SESSION_PROMPT.md` requis : oui/non
- Si `green`, statut masque dans la reponse utilisateur : oui/non/non applicable

## Plan court
1. ...

## Verification prevue
- ...
