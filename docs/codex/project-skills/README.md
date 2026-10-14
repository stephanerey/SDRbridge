# Project-local Codex skills

Ce dossier contient les skills metier Codex propres au projet.

Politique SR :
- les skills methode `aurora-*` restent globales dans `~/.codex/skills` ;
- les skills metier du projet restent ici par defaut ;
- `docs/codex/SKILL_MAP.md` doit lister les skills locales, leurs chemins et leurs declencheurs ;
- si Codex ne les auto-decouvre pas, lire explicitement le `SKILL.md` local pertinent avant de coder ;
- ne copier une skill locale vers `~/.codex/skills` que sur demande explicite ou pour une session pilote.

Structure recommandee :

```text
docs/codex/project-skills/
  codex-{project}-core/
    SKILL.md
    references/
  codex-{project}-ui/
    SKILL.md
    references/
  codex-{project}-agent-runtime/
    SKILL.md
    references/
```

Pour une skill locale liee a un agent IA runtime, appliquer `docs/codex/AI_AGENT_RUNTIME_METHOD.md` : definir l'action produit bornee, la forme runtime, la representation interne stable, les modeles types, le prompt contract, le message builder applicatif, les tools/actions, le routing/fallback, la validation stricte, les traces, les tests et la validation humaine si necessaire.

La description frontmatter d'une skill metier doit rester sous 1024 caracteres et viser 300 a 800 caracteres.
Le `short_description` dans `agents/openai.yaml` est distinct : 25 a 64 caracteres.
