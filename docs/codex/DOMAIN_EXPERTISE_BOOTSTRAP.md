# DOMAIN_EXPERTISE_BOOTSTRAP.md

## Objectif
Transformer Codex en expert senior de la verticale du projet avant qu'il modifie des fonctionnalites metier.

Ce bootstrap concerne les skills metier Codex, c'est-a-dire les skills qui guident Codex pendant le developpement. Elles sont distinctes des skills runtime injectees dans les agents IA applicatifs.

## Declenchement obligatoire
Utiliser ce bootstrap :
- a l'installation SR dans un nouveau projet ;
- apres export domaine ou handoff domaine ;
- avant une tache touchant des donnees metier, workflows, ecrans metier, agents IA, controles, validations humaines ou integration verticale ;
- si aucune skill metier Codex n'existe encore pour le projet.

## Sources a analyser
Lire les sources disponibles sans inventer :
- PRD, brief, specs produit ;
- `docs/domain/` ;
- `docs/CURRENT_STATE.md` ;
- modeles DB, migrations, schemas, OpenAPI ;
- routes backend et ecrans frontend metier ;
- exemples de donnees anonymisees ;
- exports domaine, AIP, graphe de connaissances, documentation RAG/KG ;
- tickets, runbooks, ADR, decisions humaines.

## Livrables domaine
Produire ou mettre a jour :

```text
docs/domain/DOMAIN_PROFILE.md
docs/domain/GLOSSARY.md
docs/domain/BUSINESS_RULES.md
docs/domain/RISK_REGISTER.md
docs/domain/HUMAN_VALIDATION_RULES.md
docs/codex/SKILL_MAP.md
docs/codex/project-skills/
```

## Cartographie minimale
Identifier :
- objets metier ;
- roles utilisateurs ;
- workflows ;
- actions sensibles ;
- regles critiques ;
- invariants ;
- validations humaines ;
- integrations externes ;
- donnees personnelles ou sensibles ;
- risques de mauvaise interpretation ;
- zones ou Codex doit demander validation.

## Skills Codex metier attendues
Proposer des skills par domaine recurrent, risque ou non evident.
Exemples de familles :
- `codex-{project}-core`
- `codex-{project}-ui`
- `codex-{project}-data`
- `codex-{project}-integration`
- `codex-{project}-security`
- `codex-{project}-agent-runtime`

Chaque skill doit avoir :
- declencheurs concrets ;
- regles non negociables ;
- limites ;
- references documentaires ;
- exemples utiles ;
- criteres de validation humaine.

## Regle de blocage
Si une tache touche le metier et qu'aucune skill Codex metier pertinente n'existe, Codex doit s'arreter et proposer :
- la skill a creer ;
- les sources a lire ;
- les questions a valider ;
- les risques a couvrir.

Codex ne doit pas coder silencieusement une regle metier absente.

## Validation
Les skills metier Codex doivent etre proposees avant generation, puis validees par l'humain avant installation ou usage systematique.
Elles sont locales au projet par defaut. Ne pas les copier dans `~/.codex/skills` sauf decision explicite.

## Mise a jour continue
Mettre a jour les livrables domaine et `SKILL_MAP.md` apres :
- nouvelle regle metier ;
- nouveau workflow ;
- nouvelle integration ;
- incident ou bug metier ;
- creation d'un agent IA runtime ;
- decision humaine structurante.
