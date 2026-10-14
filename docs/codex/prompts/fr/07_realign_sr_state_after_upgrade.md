# Realigner l'etat SR apres upgrade

Commencer en lecture seule. Lire `AGENTS.md`, `SR_BOOTSTRAP.md`, `CURRENT_STATE`, les registres et la reprise `selected` de `find_next_session_prompt.py`; si elle est `ambiguous`, demander le chemin et utiliser `--prompt`.

Lire le `task_state.yaml` actif ou les contrats legacy necessaires. Inventorier les exigences ouvertes, dont `validated_requests`, avec implementation, preuves et acceptation. Proposer le realignement minimal et les statuts `repair`, `user_testing` ou `blocked`.

Attendre la validation exacte `je valide` avant toute mutation. Modifier ensuite uniquement la memoire et les registres nommes, jamais le code applicatif. Mettre `CURRENT_STATE.md` a jour uniquement avec des preuves. Ne pas choisir une reprise par date, convertir l'historique en masse ou creer un micro-lot pour une exigence existante.
