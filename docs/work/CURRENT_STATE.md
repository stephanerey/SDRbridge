# État réel — SDRbridge 0.4.0 — 15 octobre 2026

## Implémenté

- Cœur RX mono-source par processus, ring SDBR v2, transport SDBU v2, profils DSP, capture/replay SigMF et contrôle local.
- Connecteurs SDR++ 1.3.0 x64, ExtIO HDSDR Win32 et shim ANTRACK, tous en lecture seule côté RF.
- Journaux JSON persistants et rotatifs, fichier de fautes natives, `run_id`, métriques de file/dispatcher et chemin visible dans Diagnostics.
- Backend Soapy générique intégré au paquet Windows via la couche ctypes, avec catalogue filtré par backend, modèle et numéro de série.
- Inventaire réel : RSPdx `2001077942`, clone RSP1 `0000000001` et backend MSi2500 ; les périphériques audio Pothos sont exclus.
- Instances nommées : configuration, logs et rings isolés ; `--port-offset` décale les ports de contrôle et UDP ; `--device-id` sélectionne explicitement le récepteur.
- Interface Qt 0.4.0 affichant la liste des SDR de la source Soapy et le nom de l'instance.
- Paquet portable et installateur `SDRbridge_Setup_0.4.0.exe`, construits à partir de la version de `pyproject.toml`.

## Preuves obtenues

- 48/48 tests applicatifs verts.
- Chaque SDR reçoit seul via Soapy à environ 1,92 MS/s, sans drop ni erreur.
- Deux processus simultanés sont verts avec le RSPdx natif (≈1,910 MS/s) et le RSP1 Soapy (≈1,934 MS/s), zéro drop/erreur sur 10 s.
- Le paquet portable énumère les deux séries physiques et termine proprement en mode CLI sans console.
- L'installateur v0.4.0 a été installé dans un dossier isolé, son exécutable chargé, les connecteurs SDR++/HDSDR vérifiés, puis il a été désinstallé sans reste.
- SHA-256 installateur : `7FD9131EB4C0EC467C22B7EE288BFA514CBE9EDC6C300DA61C5DF93C4DDC2FFB`.
- Le smoke de l'installation réelle ouvre la GUI Soapy, affiche le titre v0.4.0, puis s'arrête proprement avec le code 0 ; le conflit entre Qt embarqué 5.15.2 et Pothos Qt 5.15.3 est corrigé par l'ordre d'initialisation.

## Réserves explicites

- Deux processus utilisant tous les deux SoapySDRPlay ne tiennent pas 2 MS/s avec le module Pothos 2021 construit pour l'API SDRplay 3.07 ; le second flux tombe à environ 52 kS/s. Utiliser le mode mixte natif + Soapy sur cette machine.
- Aucune clé RTL2832 réelle ni USRP B100 n'a encore été qualifié. Leur compatibilité dépend du module Soapy correspondant (`rtlsdr` ou `uhd`).
- L'installateur n'est pas signé et n'est pas encore joint à une release GitHub.
- Le gate historique d'endurance reste ouvert : le run simulé final de 10 minutes a produit des drops tardifs, donc le run 60 minutes n'a pas été lancé.

## Reprise

1. Tester une clé RTL2832 réelle via SoapyRTLSDR, puis l'USRP B100 via UHD/Soapy.
2. Mettre à jour ou reconstruire SoapySDRPlay pour l'API 3.15, puis retester deux processus Soapy simultanés.
3. Rejouer le smoke simulé au repos, le run de 10 minutes, puis seulement l'endurance de 60 minutes.
4. Publier séparément l'installateur validé comme asset d'une release GitHub lorsque la v0.4.0 doit être diffusée aux utilisateurs.
