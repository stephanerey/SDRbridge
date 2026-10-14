# Rapport de préparation — 13 octobre 2026

## Provenance et état du dépôt

Import de43 fichiers applicatifs depuis `f5jwf/SDR_Bridge` au commit `7efd536e059e60130884e6aef3a23e1e5aea79dc`. README local préservé ; README amont reste consultable dans l'objet Git importé. Aucun commit, branche de développement ni push créé. `origin` pointe sur stephanerey/SDRbridge, `upstream` sur f5jwf/SDR_Bridge. Le dépôt est initialisé mais HEAD n'a pas encore de commit : certains outils Git/pip freeze affichent donc un avertissement. Ce n'est pas une autorisation à committer.

SR installé avec l'installeur officiel depuis tag4.1.0, commit `596a681742e664dc9fdbbdc26783d62bba3f77f0`, source locale `E:/PLDesign/SDRbridge-SR410-source`. Prévisualisation :153 changements,0conflit ; installation effectuée, règles AGENTS préservées. Backup local dans docs/codex/upgrade_backups. Contrôle post-installation initial : succès,0erreur/0avertissement. Le contrôle final après personnalisation est consigné dans CURRENT_STATE.

## Environnement observé, sans ouverture du SDR

| Élément | Observation |
|---|---|
| Windows | 11 Professionnel,10.0.26200,x64 |
| CPU/RAM | Intel i9-12900KF ;68 519 780 352 octets physiques |
| Python bridge | .venv isolé Python3.12 ; paquet amont installé en editable |
| Paquets installés pour préparation | NumPy2.5.4, PyYAML6.0.3 ; autres dépendances futures seulement résolues en dry-run |
| SDRplay | SDK/API3.15, headers et DLL x86/x64 présents ; RSPdx déclaré connecté par l'utilisateur, pas ouvert par cette tâche |
| Soapy | PothosSDR2021.07.25 ; util --info :0.8.1, API0.8.0, ABI0.8, module sdrplay0.3.0 |
| Build C++ | CMake présent ; vswhere détecte Visual Studio18 BuildTools avec composant VC x86/x64 ; compilation non effectuée |
| HDSDR | version utilisateur2.81a ; metadata exécutable2.81.0.2 ; non lancé |
| SDR++ | version utilisateur1.2.1 ; network_source.dll présent ; non lancé |
| ANTRACK local | E:/PLDesign/Antrack, HEAD d9cd6e8e4cc225cb9dc9479bb44c631c23ea8c2b, modifications utilisateur présentes, Python3.12.8 ; laissé intact |
| ANTRACK cible distante | main observé35f1c35b45d0a6a000b93d1d47fb47b6543aefcf ; distinct de l'installation locale ; divergence manifeste/README Python à traiter dans un environnement isolé |

Commande de référence : `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Résultat initial : **4 tests réussis en0,509s**, sans accès matériel. Ils ne couvrent pas la cible PRD. Le test de plafond4clients est un comportement historique à remplacer volontairement, pas un invariant produit à conserver.

Résolution pip `--dry-run` réussie pour SciPy1.18.1, PyQt5 5.15.11, PyQtGraph0.14.0, zeroconf0.151.5, jsonschema4.26.0 avec NumPy2.5.4/Python3.12 Windows64. Ce résultat n'est ni un import fonctionnel, ni une compilation des modules natifs, ni une validation des licences de distribution.

## Écarts amont → cible à traiter

| Surface | Fait observé | Lot |
|---|---|---|
| bridge/model | Limite4clients ; configuration callback insuffisamment liée à une frontière ; temps monotone hôte | CORE/RING |
| métriques | Heartbeat interprété comme lecture ; cumul reçu ajouté à nouveau | CORE/NET |
| source simulée | Convention sin/cos à expliciter et corriger avec tests de signe | CORE |
| ring | v1 header28octets, slot32 ; commit testé avant copie seulement, vues réutilisables | RING |
| ExtIO | Pointeur de shared memory donné au callback, snapshots RF à actualiser | RING/QUAL |
| ANTRACK shim | Interpolation linéaire, FIFO concaténée non bornée, config de registration vieillissante | DSP/QUAL |
| Soapy | Driver SDRplay et hypothèses RSP1A/gain spécifiques ; timestamps/flags ignorés, erreurs thread à remonter | RF |
| native SDRplay | Chemin réel distinct du vieux stub sdrplay.py ; erreur callback stockée sans propagation suffisante | CORE/RF |
| app/gui | Tkinter, import GUI à découpler du headless ; CLI expose surtout natif/simulation | UI/OPS |
| UDP | v1 fragmentation, mono-destination, pas protocole natif v2 ni profil SDR++ | NET |
| packaging | Chemins développeur codés en dur, build x64/Win32 à rendre découvrable | QUAL |
| tests | 4 tests unitaires de base, pas preuve concurrence interprocessus/DSP/matériel | Tous |

Pas de correction produit pendant cette préparation. Les versions externes sont des observations datées, pas une promesse que main reste identique. Prochaine activité autorisable : prompt de lancement, puis passes de réalisation avec tests et preuves.
