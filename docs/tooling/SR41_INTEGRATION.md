# Intégration SR Method4.1.0 — effective

Source : [tag officiel4.1.0](https://github.com/syl2042/Aurora_SR_method_codex_pack/tree/v4.1.0), commit596a681742e664dc9fdbbdc26783d62bba3f77f0. Installation effectuée avec le script officiel après prévisualisation153changements/0conflit. Règles locales AGENTS conservées, copie de sauvegarde locale ignorée par Git.

## Adaptation SDRbridge
PROJECT_PROFILE définit Windows11, Python3.12, C++17 et Qt, knowledge=core. Les scripts de navigateur du pack restent des ressources génériques non sélectionnées : ils ne valident pas la GUI native. Le runner Qt doit être livré par le lot UI ; command=null signifie preuve indisponible, jamais réussite. Contrat visuel : docs/product/DESIGN.md, non l'ancien DESIGN.md amont.

Skills méthode présentes dans docs/codex/skills-method, sans installation globale présumée. Route via SR_BOOTSTRAP/SR_ROUTES et SKILL_DIGEST ; charger seulement les skills déclenchées. La skill métier sdrbridge-engineering et ses cinq références sont locales. Aucun agent LLM embarqué dans le produit : contrat agent_runtime non requis.

Registres SR_LOTS/SR_PASSES remplis :9lots,4passes ; BASE effectué, autres proposés. Les champs validated_request_ids assurent la traçabilité des demandes, pas la validation d'une implémentation. Les preuves de conception des lots futurs restent pending et doivent être mises à jour à la lecture effective du code.

## Vérifications reproductibles
Depuis la racine dans l'environnement isolé :
- .venv/Scripts/python.exe scripts/codex/sr_post_install_check.py --root . --json
- .venv/Scripts/python.exe scripts/codex/validate_lot_contract.py --file docs/codex/SR_LOTS.yaml
- .venv/Scripts/python.exe scripts/codex/validate_pass_contract.py --file docs/codex/SR_PASSES.yaml --lots-file docs/codex/SR_LOTS.yaml
- .venv/Scripts/python.exe -m unittest discover -s tests -v

Contrôles post-personnalisation réussis,0erreur/0avertissement SR ;9lots et4passes valides. Quatre tests applicatifs amont seulement ; ne pas présenter ceci comme recette V1.

## Doctrine d'exécution
Autorisation, vérification et activation restent distinctes. Le prompt de lancement couvre explicitement les trois passes futures, sans micro-validations tant que scope/sûreté restent identiques. Il n'autorise pas pilotes, activation SDR/LAN, publication ni Nexus. Aucun enchaînement hors des passes listées.

Lire lot/code/consommateurs et preuve attendue, pas toutes les archives. Conserver un état compact de reprise, preuve proportionnée au risque, pas de tests volontairement rouges ni rollback artificiel. Réouvrir le lot concerné si une régression apparaît.

Nexus reste optionnel, inactif tant que connexion/capacités/permissions ne sont pas vérifiées ; [évaluation distincte](NEXUS_MCP_EVALUATION.md). Ne pas mélanger une éventuelle migration de méthode ultérieure avec l'implémentation V1.
