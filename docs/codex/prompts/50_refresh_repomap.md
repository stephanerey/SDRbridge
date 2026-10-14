# Rafraichir la carte du depot

Utiliser ce prompt seulement si une modification structurelle rend la carte existante trompeuse. Lire `REPO_MAP_POLICY.md`, lancer `generate_repo_map.py --write`, puis verifier le diff. Mettre `CODEBASE_MAP.md` a jour uniquement pour les points de navigation durables.

En mode `core`, aucun appel MCP. En mode `nexus_kg`, suivre `MCP_POLICY.yaml` et ne demander que la capacite de mise a jour explicitement autorisee. La carte et le KG orientent; le code reel tranche.
