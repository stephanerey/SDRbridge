# État réel — SDRbridge 0.6.0 en développement — 6 novembre 2026

## Implémenté

- Cœur RX mono-source par processus, ring SDBR v2, transport SDBU v2, profils DSP, capture/replay SigMF et contrôle local.
- Connecteurs SDR++ 1.3.0 x64, ExtIO HDSDR Win32 et shim ANTRACK, tous en lecture seule côté RF.
- Journaux JSON persistants et rotatifs, fichier de fautes natives, `run_id`, métriques de file/dispatcher et chemin visible dans Diagnostics.
- Backend Soapy générique intégré au paquet Windows via la couche ctypes, avec catalogue filtré par backend, modèle et numéro de série.
- Inventaire réel : RSPdx `2001077942`, clone RSP1 `0000000001` et backend MSi2500 ; les périphériques audio Pothos sont exclus.
- Instances nommées : configuration, logs et rings isolés ; `--port-offset` décale les ports de contrôle et UDP ; `--device-id` sélectionne explicitement le récepteur.
- Interface Qt 0.6.0 affichant la source effective, le nom de l'instance et les paramètres de chaque destination UDP.
- Paquet portable et installateur `SDRbridge_Setup_0.4.0.exe`, construits à partir de la version de `pyproject.toml`.
- Transport QMAP 0.6/Linrad UDP RX : resampling mutualisé 96 kS/s, trames fixes 1416 octets, fréquence centrale et convention spectrale QMAP ; coexistence configurée avec SDR++.
- Paquet portable 0.5.0 construit sous `release-v0.5`; Inno Setup étant absent de la machine, aucun nouvel installateur `.exe` n'a été produit.
- Source fichier IQ WAV/RF64 HDSDR/SDR++ : I/Q stéréo `uint8`, `int16`, `int32` ou `float32`, lecture temps réel, boucle optionnelle et fréquence centrale issue du nom ou d'une surcharge.
- Sélection graphique du fichier dans la liste des sources, remplacement à chaud et retour au SDR sans recréer le bridge ni ses destinations.
- Destinations UDP à débit indépendant, configurables dans l'interface avec taille de datagramme et profondeur de file ; les traitements DSP identiques sont mutualisés.
- Optimisation du chemin plein débit CS16 sans conversion flottante et pacing SDR++ sans attente active.

## Preuves obtenues

- 48/48 tests applicatifs verts.
- 51/51 tests applicatifs verts après ajout QMAP, dont vecteur de trame, agrégation, frontière de discontinuité et réception UDP intégrée à partir d'une source 2 MS/s simulée.
- 60/60 tests applicatifs verts, dont démarrage en découverte sans SDR, sélection graphique avec lecture automatique, permutation SDR/fichier, lecture de vecteurs WAV et réception simultanée vérifiée à 2 MS/s, 192 kS/s et 1 MS/s.
- Smoke du paquet 0.5.0 vert avec le RSP1A `2236027C98` : datagramme QMAP de 1416 octets, centre 144,3 MHz, `nrx=1`, données IQ non nulles.
- Chaque SDR reçoit seul via Soapy à environ 1,92 MS/s, sans drop ni erreur.
- Deux processus simultanés sont verts avec le RSPdx natif (≈1,910 MS/s) et le RSP1 Soapy (≈1,934 MS/s), zéro drop/erreur sur 10 s.
- Le paquet portable énumère les deux séries physiques et termine proprement en mode CLI sans console.
- L'installateur v0.4.0 a été installé dans un dossier isolé, son exécutable chargé, les connecteurs SDR++/HDSDR vérifiés, puis il a été désinstallé sans reste.
- SHA-256 installateur : `7FD9131EB4C0EC467C22B7EE288BFA514CBE9EDC6C300DA61C5DF93C4DDC2FFB`.
- Le smoke de l'installation réelle ouvre la GUI Soapy, affiche le titre v0.4.0, puis s'arrête proprement avec le code 0 ; le conflit entre Qt embarqué 5.15.2 et Pothos Qt 5.15.3 est corrigé par l'ordre d'initialisation.

## Réserves explicites

- Deux processus utilisant tous les deux SoapySDRPlay ne tiennent pas 2 MS/s avec le module Pothos 2021 construit pour l'API SDRplay 3.07 ; le second flux tombe à environ 52 kS/s. Utiliser le mode mixte natif + Soapy sur cette machine.
- Aucune clé RTL2832 réelle ni USRP B100 n'a encore été qualifié. Leur compatibilité dépend du module Soapy correspondant (`rtlsdr` ou `uhd`).
- L'installateur publié avec la release GitHub v0.4.0 n'est pas signé ; Windows peut afficher un avertissement SmartScreen.
- Le gate historique d'endurance reste ouvert : le run simulé final de 10 minutes a produit des drops tardifs, donc le run 60 minutes n'a pas été lancé.
- La source fichier 0.6.0 est validée sur trois enregistrements HDSDR réels int16 à 2 MS/s et sur des vecteurs SDR++ générés ; un enregistrement SDR++ réel reste à rejouer avant publication.
- Aucun paquet portable ni installateur 0.6.0 n'a encore été construit ou installé.

## Reprise

1. Tester une clé RTL2832 réelle via SoapyRTLSDR, puis l'USRP B100 via UHD/Soapy.
2. Mettre à jour ou reconstruire SoapySDRPlay pour l'API 3.15, puis retester deux processus Soapy simultanés.
3. Rejouer le smoke simulé au repos, le run de 10 minutes, puis seulement l'endurance de 60 minutes.
4. Pour chaque prochaine version, reconstruire et requalifier l'installateur avant de le joindre à la release GitHub correspondante.
5. Valider visuellement QMAP 0.6 avec **Monitor** actif sur le port 50004 et le RSP1A réel.
