# SDRbridge

Bridge RX pour partager un SDR entre plusieurs applications locales et réseau.

État au 15 octobre 2026 : application V0.3 intégrée, 39 tests applicatifs verts, binaires natifs x64/Win32 compilés et source SDR++ SDBU v2 qualifiée séparément. La recette fonctionnelle 10 min passe sur un run court, mais l'endurance AC-14 reste ouverte : une suspension Windows tardive a saturé la file source et créé des pertes simulées.

**Pour travailler avec Codex : commencer par [docs/START_HERE.md](docs/START_HERE.md).**

- [Prompt de lancement](docs/handoff/START_IMPLEMENTATION.md) : autorisation bornée et réalisation en trois passes.
- [PRD v0.3](docs/product/PRD.md) : objectifs, exigences et périmètre.
- [Contrat d'exécution](docs/specs/06_IMPLEMENTATION_BASELINE.md) : choix techniques fermés et limites.
- [Décisions et paramètres](docs/product/DECISIONS.md) : acquis, propositions et informations manquantes.
- [Lots de travail](docs/work/BACKLOG.md) : entrées, actions, livrables et preuves par lot.
- [État réel du projet](docs/work/CURRENT_STATE.md) : ce qui existe et ce qui n'a pas été exécuté.
- [Preuves de qualification](docs/verification/QUALIFICATION_REPORT.md) : rapports JSON, limites et réserves matérielles.
- [Source SDR++ SDBU v2](clients/sdrpp_sdbu_source/README.md) : DLL x64 précompilée, code C++, tests et scripts d'installation.
- [Évaluation Nexus](docs/tooling/NEXUS_MCP_EVALUATION.md) : connexion encore à vérifier.

Dépôt distant : [stephanerey/SDRbridge](https://github.com/stephanerey/SDRbridge).

Le dossier `docs/archive/` préserve le PRD v0.1 ; il ne constitue pas la spécification courante.
