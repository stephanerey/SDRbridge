# Rapport de qualification SDRbridge V0.3

## Résultat exécuté

| Domaine | État | Preuve |
|---|---|---|
| Contrats, ring, DSP, RF simulés | Implémenté et testé | `tests/` — 28/28 `unittest` |
| Réseau natif, UDP, Qt, capture/replay | Implémenté et testé | `output/qualification/smoke-bounded-metrics.json`, captures Qt |
| Native/ExtIO/ANTRACK locaux | Compilé et testé localement | `tests/test_local_clients.py`, `native/build/**` |
| Paquet portable | Compilé et smoke-testé | `release-v0.3/`, client natif : 2 919 datagrammes / 3 s |
| Fonctionnel 10 min | Échec final | `output/qualification/functional-10m-queue256.json` |
| Endurance 60 min | Non lancée | bloquée par AC-14 |
| Qualification matérielle | Non exécutée | RSPdx et logiciels tiers non activés |

Le smoke 30 s avec GUI, cinq lecteurs locaux, profils 192/96 kS/s et deux UDP passe avec zéro drop, high-water 22/64, p95 29,4 ms, mémoire 102,8 MiB et arrêt 0,42 s (`smoke-queue64.json`). Après redimensionnement justifié de la file à 256 blocs, le run 10 min final atteint 783 drops source entre 570,8 et 597,5 s, high-water 256/256 et p95 531,9 ms. Les lecteurs rapides et UDP ne signalent pas de trous ; la perte se situe dans le couple source simulée/dispatcher lors d’un rattrapage tardif Windows. Ce résultat est conservé comme échec critique, pas comme tolérance.

Un contrôle comparatif de 60 s sans boucle Qt, avec les deux profils DSP et cinq lecteurs ring, produit 29 293 blocs, zéro drop, high-water 8/256 et zéro erreur. Il renforce l’hypothèse d’une suspension/charge de l’event loop Windows dans le scénario GUI ; il ne remplace pas la recette intégrée.

## Commandes reproductibles

```powershell
cd E:\PLDesign\SDRbridge
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\run_simulation_qualification.py --duration 30 --warmup 5 --capture-seconds 5 --label smoke
.\.venv\Scripts\python.exe scripts\run_simulation_qualification.py --duration 600 --warmup 300 --capture-seconds 10 --label functional-10m
.\packaging\build_exe.ps1
```

Le run 60 min doit rester interdit tant que le run 10 min final n’est pas vert. Aucun de ces scripts ne modifie un pilote, pare-feu, RSPdx, ANTRACK ou HDSDR.

## Procédure de recette réelle

1. Relever versions de Windows, API SDRplay, pilote Soapy, CPU/RAM, architectures et interfaces réseau ; conserver les installations tierces intactes et faire une sauvegarde de leurs fichiers de configuration.
2. Démarrer d’abord le bridge avec `--source native` ou `--source soapy`, sans `--auto-start`, vérifier les capacités et l’état effectif dans la GUI, puis lancer RX.
3. Connecter manuellement ANTRACK au shim livré et vérifier 96/192 kS/s ; charger manuellement l’ExtIO dans HDSDR 2.81a ; configurer SDR++ 1.2.1 en Network Source raw CS16. Aucun client ne doit retuner le matériel.
4. Mesurer débit, qualité IQ, pertes par couche, latence corrélée, CPU/RAM et arrêt ; enregistrer les versions et les journaux. QMAP/Linrad reste hors verdict.
5. En cas d’échec, arrêter le bridge, restaurer les sauvegardes et ne modifier aucun pilote ou pare-feu sans autorisation distincte.
