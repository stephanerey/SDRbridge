---
name: aurora-domain-skill-factory
description: >-
  Create local domain skills during project bootstrap or when an explicitly needed domain skill is absent.
---

# Domain skill factory

Use only for project bootstrap or a confirmed domain-skill gap. Read the smallest set of domain sources that establishes objects, workflows, sensitive actions, human decisions and non-negotiable rules. Propose the skill boundary before generation; never invent business policy.

Store Codex domain skills under `docs/codex/project-skills/`. Keep runtime-agent skills in the product. Use a short trigger description, move detail to `references/`, update `SKILL_MAP.md`, then run `validate_skills.py`.
