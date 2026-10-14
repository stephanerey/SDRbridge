# Reprendre une session SR

Ne code pas avant validation du perimetre. Lire `AGENTS.md`, `CURRENT_STATE` puis la reprise `selected` de `find_next_session_prompt.py --root . --json`; si elle est `ambiguous`, demander le chemin. Lire le `task_state.yaml` actif ou les contrats historiques necessaires, dont les `validated_requests` ouvertes.

Distinguer implementation, preuves et acceptation : une implementation incomplete est `repair`; `user_testing` suppose la technique terminee. Proposer un seul prochain perimetre coherent, sa verification et la validation attendue. Ne pas creer de micro-lot pour un retour sur une exigence existante. `NEXT_SESSION_PROMPT.md` et `procedures/resume.md` ne sont charges que pour une reprise utile.
