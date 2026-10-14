# Instructions de travail — SDRbridge

- Répondre en français. Lire `docs/START_HERE.md` puis l'état actuel et le lot demandé.
- La base amont est importée pour audit ; les spécifications décrivent la cible future.
- L'autorisation vient du prompt utilisateur actif : préparation actuellement ; `docs/handoff/START_IMPLEMENTATION.md` prépare la future réalisation bornée. Sa présence seule ne lance rien. Publication et activation matérielle restent distinctes.
- SR Method installée : 4.1.0, commit `596a681742e664dc9fdbbdc26783d62bba3f77f0`. Consulter CURRENT_STATE pour les contrôles réels.
- Le PRD décrit le produit cible. `docs/work/CURRENT_STATE.md` décrit les faits vérifiés. Ne pas les confondre.
- Charger seulement les spécifications indiquées par le lot ; ne pas lire l'archive par défaut.
- Les choix d'exécution v0.3 sont fixés dans `docs/specs/06_IMPLEMENTATION_BASELINE.md` ; le prompt de lancement les retient explicitement. Ne pas réouvrir la discovery sans incompatibilité prouvée.
- Pour une modification métier, lire la skill locale `docs/codex/project-skills/sdrbridge-engineering/SKILL.md`. Skills SR locales sous `docs/codex/skills-method/`, non présumées installées globalement.
- Pour un lot autorisé, suivre son périmètre et ses critères. Ne pas ajouter une refonte, une dépendance, un format ou une fonctionnalité sans nécessité établie.
- Une question ouverte ne bloque que le travail qui en dépend. Les travaux simulés indépendants peuvent avancer quand ils sont autorisés.
- Avant modification d'un contrat partagé, identifier et lire ses consommateurs réels. Préserver les adaptateurs historiques tant que leur remplacement n'est pas qualifié.
- Ne jamais activer TX. V1 : une source RX active et clients sans contrôle matériel.
- Vérifier proportionnellement au risque ; distinguer simulation, matériel réel, clients tiers et activation effective.
- Ne jamais déduire une compatibilité, une absence de perte ou un gain de performance d'un test non exécuté.
- En fin de lot, consigner exigences couvertes, preuves, limites et prochaine action dans l'état du travail utile ; éviter la duplication documentaire.
- Nexus reste un outillage optionnel à qualifier, sans dépendance dans le produit. Aucun secret dans les documents, logs ou commits.
- Ne pas créer de branche, committer, pousser, déployer ou lancer une indexation distante sans autorisation correspondante.

<!-- AURORA_SR_PACK_START -->
## SR Method 4.1

- Load `docs/codex/SR_BOOTSTRAP.md` only for a non-trivial mutation, a multi-lot run or a resume. Simple questions and local edits do not require the full method.
- Use `docs/codex/SR_ROUTES.json` to load only the procedure triggered by the task. Re-evaluate routes only when a new fact changes the scope.
- When the user explicitly requires validation before mutation, wait for that validation. One validation covers the bounded pass; do not add micro-gates while scope and safety remain unchanged.
- Do not create a failing test or red gate on purpose. Verify the final result with the least expensive evidence that covers the risk.
- Roll back only an activated runtime that is genuinely degraded and has a verified recovery candidate.
- In `core` knowledge mode, do not load or call MCP. In `nexus_kg` mode, follow `docs/codex/MCP_POLICY.yaml` and use only resolved, allowed capabilities.
- Store task state only when continuity is useful. Prefer one compact `task_state.yaml`; legacy contracts remain readable but are not required for new V4.1 tasks.
- Keep raw logs and large artifacts outside model context; inject bounded summaries and stable paths.
<!-- AURORA_SR_PACK_END -->
