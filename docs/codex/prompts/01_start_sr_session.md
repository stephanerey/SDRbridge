# Reprendre une session SR

Ne code pas avant validation du perimetre.

1. Lire `AGENTS.md`, `docs/CURRENT_STATE.md` si present, puis lancer `find_next_session_prompt.py --root . --json`.
2. Utiliser la reprise `selected`; si elle est `ambiguous`, demander le chemin exact. Ne jamais choisir selon la seule date.
3. Lire le `task_state.yaml` actif ou, pour une tache historique, uniquement les contrats et fichiers necessaires. Recharger les exigences ouvertes, y compris `validated_requests` legacy.
4. Distinguer implementation, preuves et acceptation humaine. Une implementation incomplete est `repair`; `user_testing` suppose la technique terminee.
5. Proposer un seul prochain perimetre coherent, ses limites, sa verification finale et la validation humaine attendue.

Ne pas recreer un micro-lot pour un retour sur une exigence existante : rouvrir le lot d'origine si necessaire. `NEXT_SESSION_PROMPT.md` et `procedures/resume.md` servent uniquement quand une reprise est utile.
