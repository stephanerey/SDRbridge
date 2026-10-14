# Skill router — SR Method 4.1

Load a skill only when its exact trigger applies. Normal tasks use zero to two method skills; complex tasks use at most three.

| Skill | Exact trigger |
|---|---|
| `aurora-lot-runner` | Execute a validated multi-lot pass, a long resume or a bounded autonomous phase. |
| `aurora-diagnose` | Explain or correct an observed bug, runtime error, failed test or integration problem. |
| `aurora-architecture-check` | Make a durable structural decision: schema, migration, dependency, external integration or orchestration boundary. |
| `aurora-ui-visual-qa` | Validate a significant UI change visually or through an existing browser path. |
| `aurora-to-prd` | Explicit product discovery when the request is not implementable as stated. |
| `aurora-domain-skill-factory` | Project bootstrap or explicit absence of a needed local domain skill. |

The following are harness mechanisms, not cognitive skills: planning files, terminal compaction, final diff review, RepoMap refresh and test selection. SR 4.1 does not provide a TDD skill and never requires an intentionally failing test.

Project business skills stay local under `docs/codex/project-skills/`. Runtime-agent skills are product artifacts, not global Codex skills.

SDRbridge : lire `docs/codex/project-skills/sdrbridge-engineering/SKILL.md` pour changements RX/IQ/DSP/ring/clients/capture. Les six skills méthode sont présentes sous `docs/codex/skills-method/` ; leur présence locale ne garantit pas une installation globale. Aucune skill produit LLM nécessaire : SDRbridge n'embarque pas d'agent IA.
