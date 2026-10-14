# Générer les skills métier validées

Génère uniquement les skills locales validées pour ce projet, sous `docs/codex/project-skills/`.

Chaque `SKILL.md` doit avoir un déclencheur précis, une responsabilité bornée et des instructions courtes. Place les connaissances volumineuses dans `references/` et évite de recopier les procédures SR ou la documentation métier déjà canonique.

Ne crée ni skill globale, ni agent runtime, ni dépendance MCP implicite. Mets à jour la carte locale des skills si elle existe, puis exécute `python3 scripts/codex/validate_skills.py` ou le validateur équivalent du dépôt. Rapporte les fichiers créés et le résultat de validation.
