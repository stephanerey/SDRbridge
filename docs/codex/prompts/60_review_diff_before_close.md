# Verification finale avant cloture

Lire la demande validee et le diff reel. Verifier que le scope est respecte, que les changements locaux preexistants sont preserves et qu'aucune dependance, migration, secret ou action externe hors perimetre n'a ete ajoutee.

Choisir la preuve finale la moins couteuse qui couvre le risque : controle statique pour une documentation, test cible pour un comportement, build pour un artefact modifie, smoke runtime pour une activation, E2E authentifie ou validation humaine seulement lorsque requis. Ne pas creer un test rouge volontaire ni rejouer des erreurs artificielles.

Si une interface significative change, joindre la preuve visuelle prevue. Si un contrat partage change, verifier ses consommateurs. Mettre `task_state.yaml`, `CURRENT_STATE.md` ou la carte du depot a jour seulement si le changement rend leur etat actuel faux.

Rapporter : resultat, fichiers touches, preuve executee, couches non verifiees et acceptation humaine restante. `done` exige l'implementation et les preuves techniques requises; `user_testing` signifie que seule l'acceptation reelle reste.
