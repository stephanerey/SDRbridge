# Realigner l'etat SR apres upgrade

Commencer en lecture seule. Une autorisation d'upgrade ne vaut pas autorisation de modifier l'etat produit.

1. Lire `AGENTS.md`, `docs/codex/SR_BOOTSTRAP.md`, `CURRENT_STATE`, les registres et la reprise `selected` de `find_next_session_prompt.py --root . --json`. Si le resultat est `ambiguous`, demander le chemin puis utiliser `--prompt`.
2. Lire le `task_state.yaml` actif ou les contrats legacy necessaires. Inventorier les exigences ouvertes, y compris `validated_requests`, leur implementation, leurs preuves et leur acceptation.
3. Proposer un realignement minimal : lot d'origine a rouvrir, statut `repair`, `user_testing` ou `blocked`, preuves manquantes et prochaine action.
4. Attendre la validation exacte `je valide` avant toute mutation.
5. Apres validation, modifier uniquement la memoire et les registres nommes; ne toucher a aucun code applicatif.

Mettre `CURRENT_STATE.md` a jour seulement si les preuves soutiennent le nouvel etat. Ne jamais selectionner une reprise par simple date, convertir les historiques en masse, ni creer un nouveau lot pour un defaut deja rattache a une exigence existante.
