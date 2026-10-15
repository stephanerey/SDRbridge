# Vérification locale — 15 octobre 2026

## Cible

- SDR++ 1.3.0 : `E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64`
- `sdrpp_core.dll` : PE x64, linker 14.44, horodatage de build 25 mars 2026 02:47:55 UTC
- En-têtes officiels : commit SDR++ `a6df4d58e5f6b3045883a70aeb8fb41fd5dbf1d9` du 23 mars 2026
- Compilateur local : MSVC 19.43.34808, ABI binaire compatible MSVC 14.x

## Preuves exécutées

1. Build CMake x64 Release réussi.
2. `ctest -C Release --output-on-failure` : `sdbu_protocol_tests`, 1/1 vert.
3. Exports DLL présents : `_INFO_`, `_INIT_`, `_CREATE_INSTANCE_`, `_DELETE_INSTANCE_`, `_END_`.
4. Dépendances résolues dans le paquet SDR++ : `sdrpp_core.dll`, `volk.dll`, runtimes MSVC et `WS2_32.dll`.
5. Chargement réel : `sdbu_source.dll` observée dans le processus SDR++ 1.3.0 et instance `SDRbridge SDBU v2` initialisée.
6. E2E simulé, sans ouverture du RSPdx : SDRbridge a émis SDBU v2 en loopback ; SDR++ a journalisé la réception du stream 1, epoch 1, CS16, 2 000 000 S/s, 144 300 000 Hz, puis a réglé son DSP à 2 000 000 S/s.
7. E2E réel de la correction de fréquence : la DLL 0.1.1 a suivi SDRbridge à 137 000 000 Hz, puis la DLL finale installée a été revalidée à 433 400 000 Hz. Dans les deux cas, le sélecteur supérieur, le VFO et le waterfall SDR++ affichaient exactement la fréquence du bridge. Aucun réglage RF n'a été envoyé depuis SDR++.

## Artefact publié et installation testée

- DLL : `E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64\modules\sdbu_source.dll`
- Version DLL : 0.1.1
- SHA-256 de `bin/sdbu_source.dll` reconstruit depuis ce répertoire : `3C769DB1E7BE3F470AD7E50BFCED5C2430DA2114EA7A18C0CD24F1639C3CED12`
- SHA-256 de la build installée et testée visuellement : `03FB4120BFFA5D13A11876E99188C6296F6848CFD0B8572D50160F9F932BE9A8` (mêmes sources ; le chemin de build MSVC rend les binaires non identiques octet pour octet).
- Source sélectionnée : `SDRbridge SDBU v2`
- Écoute finale : `127.0.0.1:7355`
- Configuration SDRbridge préparée pour le prochain démarrage : destination `127.0.0.1:7355`, transport `sdbu_v2`
- Retour arrière : manifeste `sdbu_source.install.json` et sauvegarde du `config.json` antérieur

## Limites restantes

- Le test E2E du point 6 utilise la source simulée ; l'observation matérielle du point 7 ne constitue pas une qualification complète du RSPdx ni de l'API SDRplay.
- Toute mise à jour du cœur SDR++ exige une nouvelle compilation et une nouvelle qualification de la DLL.
- La synchronisation visuelle de fréquence a été vérifiée directement dans les fenêtres SDRbridge et SDR++.

