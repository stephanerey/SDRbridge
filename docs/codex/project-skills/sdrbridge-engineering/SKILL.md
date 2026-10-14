---
name: sdrbridge-engineering
description: "Appliquer les invariants SDRbridge lors des changements acquisition RX, flux IQ, mémoire partagée, DSP, profils RF, transports, clients ANTRACK/ExtIO et capture SigMF ; sélectionner les contrats et preuves du lot sans recharger toute la discovery."
---

# SDRbridge engineering
Lire le lot actif et S6, puis uniquement la section métier nécessaire.
- Acquisition : S1 et S2 ; ne pas confondre demandé/effectif, temps matériel/hôte ou source/session/profil.
- Ring/clients : S2 et S6 §3 ; relire tous les consommateurs Python/C++ avant mutation ABI, vérifier copie et durée de vie.
- DSP : S3 et S6 §4 ; état continu, conversion saturée, oracle et gabarit mesurés.
- Réseau : S4 et S6 §5 ; parsing borné, contrôle lecture seule, natif distinct des protocoles tiers.
- Capture/headless : S5 et S6 §6 ; fichiers non écrasés, interruptions honnêtes, pas de Qt dans le cœur.
- GUI : S1 et DESIGN ; prouver la continuité du flux lors du changement de mode.
Utiliser les fichiers sous docs/specs à la racine du dépôt ; les références sont routées dans docs/START_HERE.md.
Avant clôture : exigences touchées, tests réellement exécutés, risque restant, preuve matérielle distincte.
Ne jamais activer le SDR pour un test supposé simulé. Conserver le backend natif jusqu'à qualification du remplacement.
