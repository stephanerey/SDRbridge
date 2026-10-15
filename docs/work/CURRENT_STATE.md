# État réel — 15 octobre 2026

## Implémenté

- Cœur RX V1 à source unique : contrats de flux, époques, temps, configuration versionnée et récupération watchdog.
- Ring SDBR v2 aligné avec helper atomique natif, lecteurs Python/ExtIO possédés et profils sans plafond arbitraire de clients.
- DSP CS16/CF32 et FIR polyphase streaming 2 MS/s → 192/96 kS/s, mutualisé entre consommateurs ; profils ANTRACK, natif et SDR++ raw séparés.
- Source simulée déterministe S6, Soapy générique et backend SDRplay conservé sans activation matérielle.
- Contrôle JSON natif v1 strict, baux, deux unicast loopback, SDBU v2 72 octets, raw SDR++ et client natif.
- GUI Qt normale/compacte avec FFT unique, configuration effective/brouillon, diagnostics, capture/replay SigMF 1.2.6 et configuration atomique.
- File source bornée configurable à 256 blocs (≈524 ms à 2 MS/s), high-water et pertes exposés ; aucune perte n’est remise à zéro.
- Packaging PyInstaller 6.22.3 portable V0.3, connecteurs déposés dans le paquet uniquement, sans écriture HDSDR/ANTRACK.
- Source SDR++ 1.3.0 `SDRbridge SDBU v2` versionnée sous `clients/sdrpp_sdbu_source` : DLL x64 précompilée, parseur borné CS16/CF32, taux et fréquence effective synchronisés, contrôle RF client refusé.
- ExtIO HDSDR 2.81a versionnée sous `native/extio_bridge` : DLL Win32 précompilée, copies SDBR v2 possédées, notifications de taux/LO et refus des demandes de syntonisation clientes.

## Preuves obtenues

- `.venv\Scripts\python.exe -m unittest discover -s tests -v` : 39/39 verts le 15 octobre 2026 ; le test ANTRACK utilise un port de contrôle éphémère et ne se connecte plus au bridge matériel actif.
- `clients\sdrpp_sdbu_source\scripts\build.ps1` : build Release x64 réussi ; CTest du protocole SDBU, 1/1 vert ; DLL publiée SHA-256 `3C769DB1E7BE3F470AD7E50BFCED5C2430DA2114EA7A18C0CD24F1639C3CED12`.
- Liaison SDR++ réelle observée avec le bridge déjà actif : 2 MS/s CS16 et fréquence effective identique à 137,0 MHz puis 433,4 MHz dans le sélecteur, le VFO et le waterfall SDR++. Cette observation ne vaut pas qualification matérielle complète.
- Réception simultanée réelle illustrée dans `docs/assets/sdrbridge-three-clients.png` : deux SDR++ SDBU v2 et HDSDR ExtIO affichent le même spectre fourni par SDRbridge ; HDSDR suit la fréquence centrale effective à 135,2 MHz.
- Builds natifs : helper ring x64 et Win32, SDRplay bridge x64, ExtIO Win32 + smoke multiprocessus.
- Captures Qt Windows 100/150/200 % lisibles : `output/qt/windows200`.
- Compatibilité locale : shim ANTRACK et ExtIO reçoivent des copies SDBR v2 ; client natif figé reçoit 2 919 datagrammes en 3 s.
- Smoke intégré 30 s : vert avec zéro drop, cinq lecteurs rapides, deux UDP, capture et GUI.
- Run fonctionnel 10 min avec file 64 : vert mais non retenu comme preuve finale après changement de configuration de file.

## Gate critique ouvert

Le run 10 min final avec file 256 a échoué tardivement : 783 drops source entre 570,8 et 597,5 s, high-water 256/256 et latence p95 531,9 ms. Les cinq lecteurs ring et les deux récepteurs UDP n’ont pas détecté de perte, ce qui localise le problème dans le rattrapage de la source simulée après une suspension Windows/dispatcher. L’endurance 60 min n’a donc pas été lancée. AC-14 reste `blocked`, et aucune qualification de performance nominale ne doit être annoncée.

Le contrôle sans Qt de 60 s reste vert (29 293 blocs, zéro drop, high-water 8/256), ce qui isole la réserve au scénario intégré GUI/Windows plutôt qu’au ring ou au DSP.

## Réserves matérielles explicites

- Le RSPdx/SDRplay était déjà actif lors de la vérification SDR++ ; aucun pilote, réglage système ou TX n'a été modifié. La qualification matérielle complète et les horloges restent ouvertes.
- ANTRACK n’a pas été modifié. La source personnalisée SDR++ 1.3.0 et l’ExtIO HDSDR 2.81a ont été installées séparément pour les observations réelles ; le binaire ExtIO final avec refus explicite de `SetHWLO` a passé le smoke automatisé mais n’a pas été rechargé dans HDSDR pendant cette passe documentaire.
- Le paquet portable PyInstaller n'a pas été reconstruit pour cet état source du 15 octobre.
- Le backend générique SoapySDR est présent dans le code, et PothosSDR expose localement la factory `rtlsdr`, mais la couche Python Soapy n'est pas encore embarquée dans le paquet Windows ; aucune clé RTL2832 réelle n'a été détectée ni qualifiée.
- QMAP/Linrad TIMF2, LAN/VPN et pare-feu restent hors verdict.
- L’avertissement PyInstaller `MSVCR90.dll` provient de l’API SDRplay installée et doit être vérifié avec le matériel réel.

## Reprise

1. Profiler et corriger le couple source simulée/dispatcher sous suspension Windows, sans masquer les pertes ni augmenter encore arbitrairement la file.
2. Relancer 10 min fonctionnelles, puis 60 min avec les mêmes critères S6.
3. Rebuilder le paquet portable et exécuter la procédure matérielle documentée dans `docs/verification/QUALIFICATION_REPORT.md`.
