# Prompt de lancement — SDRbridge v0.3

Le texte suivant est prêt à transmettre dans une tâche Codex ouverte sur **E:\PLDesign\SDRbridge**. Ce fichier prépare l'autorisation ; sa simple présence ne lance pas la réalisation.

---

Implémente SDRbridge dans ce dépôt jusqu'à une version intégrée et testée en simulation, prête pour la recette matérielle. Ne recommence pas la discovery ni la rédaction du PRD. La base amont et SR Method4.1.0 sont déjà importés ; conserve les fichiers locaux et ne réinitialise pas le dépôt.

## Contrat et autorisation

Lis AGENTS.md, docs/START_HERE.md, docs/work/CURRENT_STATE.md, le PRD et docs/specs/06_IMPLEMENTATION_BASELINE.md. Je retiens les choix d'exécution S6, y compris Python3.12, migration versionnée du ring, FIR avec état, réseau v2 séparé des profils tiers, et SigMF1.2.6. Applique ensuite seulement les spécifications et le code nécessaires au lot actif.

Je t'autorise explicitement à réaliser les passes SDB-PASS-002, 003 et 004 du registre SR, dans cet ordre, sans redemander la permission entre lots ni entre ces trois passes si leurs préconditions et preuves sont satisfaites. L'autorisation est bornée à ce périmètre, pas à des extensions futures. La passe001 est la préparation déjà effectuée ; vérifie son état sans refaire l'import.

Tu peux modifier les sources/tests/documents/builds de ce dépôt, installer dans son .venv les dépendances listées dans S6 et leurs transitives, construire les DLL x64/Win32 avec les outils présents, créer des fixtures/captures simulées dans un dossier de test et exécuter les tests/mesures loopback. Un clone ANTRACK du commit épinglé est autorisé uniquement sous output/compat/ pour vérification isolée, sans modification du dépôt ANTRACK existant. Préserve toute modification utilisateur.

Pas de commit, branche supplémentaire, push, publication, installation système, modification des pilotes/pare-feu, activation du RSPdx, remplacement de DLL dans HDSDR/ANTRACK installé, ni appel/indexation Nexus sans autorisation distincte. Réseau loopback autorisé ; activation LAN/VPN reste séparée.

## Exécution SR4.1

Utilise SR_BOOTSTRAP, les routes et aurora-lot-runner pour cette exécution multi-lots ; les skills sont locales dans docs/codex/skills-method. Charge la skill métier locale sdrbridge-engineering. Le profil est Windows/Python/Qt et knowledge=core : pas de dépendance MCP, pas de validation Playwright factice.

Avant chaque passe : lire les fichiers réellement touchés et leurs consommateurs, vérifier dépendances/préconditions, mettre à jour preuves de conception et statuts SR. Cette autorisation permet de valider la passe prête ; elle ne transforme pas une preuve manquante en succès. Exécuter les lots selon SR_LOTS/SR_PASSES et le backlog détaillé.

- Passe002 : CORE, RING, DSP, RF. Produire cœur/session, ring sûr avec lecteurs, traitements partagés, Soapy générique et règles RF ; tester en simulation/faux backend.
- Passe003 : NET, UI, OPS. Intégrer contrôle/données réseau, récepteur natif, profil SDR++ raw, Qt normal/compact, presets/headless/watchdog et SigMF/replay.
- Passe004 : QUAL. Exécuter recette intégrée, endurance simulée, packaging isolé et matrice clients. Préparer les étapes matérielles sans les lancer.

Les quatre tests amont sont une baseline, pas une recette suffisante ; remplacer le test de limite4clients par le comportement cible. Ajouter les tests nécessaires dans la suite existante. Faire passer les preuves du lot avant le suivant ; deux tentatives de réparation autonomes maximum par blocage, puis consigner cause et reprise sans masquer un échec.

Aucune étape critique simulée ne doit être contournée pour « avancer ». Une attente de recette matérielle ne bloque que cette recette : terminer les lots indépendants et garder le statut user_testing approprié. Si un test exige interaction Windows indisponible, livrer une procédure et marquer la preuve manquante, pas pass.

## Résultat attendu

Application complète pour le périmètre V1 documenté hors QMAP différé et qualifications matérielles non autorisées : démarrage GUI/headless, simulation/replay, acquisition implémentée, profils RF et DSP, cinq lecteurs minimum sans plafond arbitraire, réseau natif/SDR++ configurables, capture, diagnostic et arrêt propre.

Livrer configuration d'exemple et schémas validés, tests reproductibles, build/install de test, commandes de lancement, rapport REQ-001..034 ↔ preuves AC-01..17 et compatibilités, limites précises. Aucun bouton de succès factice ni fonctionnalité annoncée sur un stub. Afficher les fonctions indisponibles honnêtement.

Maintenir un état compact de reprise et des mises à jour courtes. Si le contexte devient insuffisant, enregistrer exactement lot actif, fichiers, tests et prochaine commande ; ne pas annoncer toute l'application terminée. À la fin, distinguer implémenté, testé en simulation, compilé et qualifié matériel. Me demander ensuite seulement la recette réelle manquante.

---
