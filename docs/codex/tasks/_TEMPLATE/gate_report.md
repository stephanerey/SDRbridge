# Gate Report

## Lot

- Lot ID :
- Titre :
- Statut avant :
- Statut apres :

## Evidence Gate

- Statut : OK / KO / N/A
- Fichiers ou sources lus :
- Faits verifies :
- Hypotheses restantes :
- Questions bloquantes :
- Recommandations donnees uniquement apres verification locale possible : oui/non

## Fact Gate

- Statut : OK / KO / N/A
- Classification de la reponse : `opinion/methode` / `fait_verifiable` / `hypothese_non_verifiee`
- Faits verifiables affirmes :
- Sources consultees avant conclusion :
- Sources accessibles mais non consultees :
- Hypotheses non verifiees restantes :
- Verification minimale si hypothese :
- Conclusion factuelle autorisee : oui/non

## Lot Design Evidence Gate

- Statut : OK / KO / N/A
- Requis pour statut executable : oui/non
- Lecture code requise : oui/non
- Fichiers candidats :
- Fichiers reellement lus :
- Symboles, routes, services ou schemas verifies :
- Tests ou logs consultes :
- Hypotheses restantes :
- Questions bloquantes :
- Raison si N/A :
- Statut maximal autorise si KO : `proposed`

## Backlog Mutation Gate

- Statut : OK / KO / N/A
- Fonction structurante detectee : oui/non
- Mutation backlog requise : oui/non
- `SR_INBOX.yaml` mis a jour : oui/non/N/A
- `SR_LOTS.yaml` mis a jour : oui/non/N/A
- Lots affectes :
- Lots crees :
- Lots rouverts :
- Lots bloques :
- Lots remplaces :
- Raison si aucune mutation :
- Decision de sequence :

## Global Impact Gate

- Statut : OK / KO / N/A
- Requis : oui/non
- Surfaces produit/code revues :
- Lots impactes :
- Nouveaux lots a creer :
- Lots a rouvrir, bloquer, reporter, decouper ou remplacer :
- Hypotheses restantes :
- Questions bloquantes :
- Recommandation de sequence :

## Lot Dependency Reconciliation

- Statut : OK / KO / N/A
- Lots relus :
- Lots `unaffected` :
- Lots `impacted` :
- Lots `blocked_by` :
- Lots `reopened` :
- Lots `superseded` :
- Lots `split_required` :
- Lots `depends_on` :
- Champs backlog mis a jour :

## Propagation Gate

- Statut : OK / KO / N/A
- Requis : oui/non
- Declencheur :
- Niveau de risque : low / medium / high / critical / not_applicable
- Changement annonce avant mutation : oui/non/N/A
- Validation humaine requise : oui/non
- Validation humaine recue : oui/non/N/A
- Symboles ou contrats modifies :
- Ancien contrat :
- Nouveau contrat :
- Consommateurs detectes avant mutation :
- Surfaces a risque :
- Strategie de compatibilite :
- Recherches de references executees :
- References restantes :
- References ignorees avec justification :
- Consommateurs verifies :
- Verifications executees :
- Decision : pass / repair / blocked / not_applicable
- Cloture `done` autorisee : oui/non

## Pass Planning Gate

- Statut : OK / KO / N/A
- Requis : oui/non
- Passe :
- Lots inclus :
- Ordre d'execution :
- Dependances satisfaites :
- Preflight commun :
- Validations humaines :
- Secrets/actions externes :
- Migrations :
- E2E groupe :
- Stop conditions :
- Validation `validate_pass_contract.py` :
- Decision :

## Pass Runtime Goal

- Requis : oui/non
- Fichier : `docs/codex/tasks/YYYY-MM-DD_slug/pass_runtime_goal.md`
- Generation `build_pass_runtime_goal.py` :
- Goal Length Gate :
- `max_goal_command_chars` : 1000
- `hard_limit` : 4000
- `goal_command_chars` :
- Commande `/goal` lancee/proposee :
- E2E groupe protege : oui/non/N/A
- Enchainement de passe suivante bloque sans validation : oui/non/N/A
- Decision : pass / fail / not_applicable

## Lot Completion Gate

- Statut : OK / KO / N/A
- Lot/passe valide explicitement : oui/non
- Source de validation :
- Perimetre valide relu avant cloture : oui/non
- Reduction silencieuse detectee : oui/non
- Exigence UI/UX explicite : oui/non
- Preuve visuelle ou E2E ciblee :
- Registre `validated_requests` granulaire : oui/non
- Table derivee automatiquement du registre : oui/non

| Demande utilisateur | Implementation | Preuve | Decision | Reste a faire |
|---|---|---|---|---|
| ... | not_started/partial/complete/defective | missing/partial/failed/sufficient/user_accepted | done/user_testing/repair/blocked | ... |

- Exigences partielles :
- Exigences non faites :
- Exigences bloquees :
- Exigences en attente E2E :
- Decision de statut autorisee : `done` / `user_testing` / `repair` / `blocked`
- Langage de cloture coherent avec le gate : oui/non
- Cloture `done` autorisee : oui/non

## Reprise et consolidation

- Classification : `existing_requirement_repair` / `existing_requirement_clarification` / `existing_requirement_acceptance` / `new_requirement` / `scope_change` / `cancelled_requirement`
- Requirement ID rattache :
- Contrat parent :
- Exigences ouvertes heritees :
- Lots rouverts :
- Nouveau lot cree : oui/non
- Justification hors scope si oui :
- Prochain ensemble coherent :

## Knowledge Gate

- Statut : OK / KO / N/A
- Mode : `core` / `nexus_kg`
- RepoMap consulte :
- KG Nexus consulte :
- Fraicheur KG verifiee :
- Fichiers candidats identifies :
- Fichiers reellement relus :
- KG / RepoMap a mettre a jour :

## Scope Gate

- Statut : OK / KO / N/A
- `allowed_paths` respectes :
- `forbidden_paths` touches :
- Commentaire :

## Spec Gate

- Statut : OK / KO / N/A
- Criteres d'acceptation couverts :
- Criteres incomplets :

## Design Gate

- Statut : OK / KO / N/A
- Sources design lues :
- Composants/patterns utilises :
- Patterns interdits evites :
- Screenshot ou smoke visuel :

## UI Test Readiness Gate

- Statut : OK / KO / blocked / N/A
- Requis pour le lot :
- Base URL :
- Routes demandees :
- Auth requise :
- Mode auth :
- storageState disponible :
- storageState valide :
- Redirection login detectee :
- Decision : pass / fail / blocked / not_applicable

## UI Visual Evidence Gate

- Statut : OK / KO / blocked / N/A
- Rapport : `output/playwright/ui-verification-report.json`
- Routes testees :
- Viewports testes :
- Screenshots :
- `console.error` :
- `pageerror` :
- `requestfailed` :
- Overflow horizontal :
- Redirection login inattendue :
- Decision : pass / repair / blocked / not_applicable

## Security Gate

- Statut : OK / KO / N/A
- Secrets ou donnees sensibles :
- Action critique :
- Validation humaine requise :

## Architecture Gate

- Statut : OK / KO / N/A
- DB/migration :
- Dependances :
- Service/runtime/RAG/Nexus :
- Rollback :

## Verification Gate

- Statut : OK / KO / N/A
- Commandes executees :
- Resultats :
- Verifications impossibles :

## Self Evaluation Gate

- Statut : OK / KO / N/A
- Objectif initial couvert :
- Ce que le code fait maintenant :
- Preuves :
- Risques restants :
- Ce qui aurait pu etre oublie :
- Fichiers relus apres patch :
- Decision de statut : `done` / `user_testing` / `repair` / `blocked`

## Loop Contract

- Statut : OK / KO / N/A
- Fichier : `docs/codex/tasks/YYYY-MM-DD_slug/loop_contract.json`
- Validation executee :
- Resultat :
- Si `user_testing`, liste E2E concrete presente : oui/non/N/A
- Si code applicatif modifie, `changed_files` et verifications declares : oui/non/N/A

## Tests E2E utilisateur a faire

- Parcours 1 :
- Parcours 2 :
- Donnees ou compte de test :
- Resultat attendu :
- Statut apres test utilisateur attendu : `user_testing` / `done`

## Diff Gate

- Statut : OK / KO / N/A
- Diff coherent :
- Refactor hors scope :
- Fichiers a surveiller :

## Context Budget Gate

- Statut : OK / KO / N/A
- Rapport `context_budget_report.py --root . --compact` :
- Pourcentage contexte :
- Statut contexte hybride : green / yellow / orange / red / unknown / stale / ambiguous
- Selection session fiable : oui/non
- Session utilisee :
- CWD session :
- Input tokens :
- Cached input tokens :
- Uncached input tokens :
- Cache ratio :
- Output tokens :
- Reasoning tokens :
- Rate limits :
- Signaux hybrides :
- Lots executes dans cette passe :
- Contexte sain pour continuer : oui/non
- Dernier `NEXT_SESSION_PROMPT.md` detecte au demarrage :
- `CURRENT_STATE.md` a mettre a jour :
- `NEXT_SESSION_PROMPT.md` cree/mis a jour :
- Handoff recommande :
- Raison si aucun handoff ou prompt de reprise :
- Decision conversation : continuer ici / recommander nouvelle conversation / stopper pour nouvelle conversation
- Raison decision conversation :
- Chemin `NEXT_SESSION_PROMPT.md` si cree/mis a jour :
- Prompt court fourni si reprise requise :

## Decision

- [ ] Continuer lot suivant
- [ ] Continuer jusqu'au maximum de 3 lots tant que gates verts
- [ ] Reparations necessaires
- [ ] Stop validation humaine
- [ ] Stop blocker technique
- [ ] Passer en `user_testing`

## Prochaines actions

-

## Cloture utilisateur recommandee

- Ce qui est fait :
- Resultat observe :
- Couverture du lot valide :
- Lecture expert / produit :
- Verifications executees :
- Memoire SR mise a jour :
- Loop Contract :
- Tests E2E utilisateur a faire :
- Prochaine etape recommandee :
