# ExtIO SDRbridge pour HDSDR

Cette DLL Win32 permet à HDSDR de lire le flux IQ local de SDRbridge. Elle s’enregistre auprès du bridge sur `127.0.0.1:47631`, ouvre le ring partagé SDBR v2, livre des copies IQ `CS16` possédées par le callback ExtIO et synchronise le taux ainsi que la fréquence centrale affichés par HDSDR.

Le contrôle reste volontairement en lecture seule : HDSDR ne peut pas modifier la fréquence du SDR. Lorsqu’il demande une autre valeur de LO, la DLL conserve et republie la fréquence effective de SDRbridge.

## Installer

La DLL Win32 précompilée se trouve dans [`bin/ExtIO_SDR_Bridge.dll`](bin/ExtIO_SDR_Bridge.dll). Fermer HDSDR, ouvrir PowerShell en tant qu’administrateur depuis la racine du dépôt, puis exécuter :

```powershell
.\native\extio_bridge\scripts\install.ps1
```

Pour une installation HDSDR portable ou placée ailleurs :

```powershell
.\native\extio_bridge\scripts\install.ps1 -HdsdrRoot 'D:\Radio\HDSDR'
```

Le script sauvegarde une DLL homonyme existante et écrit un manifeste de retour arrière. Pour restaurer l’état précédent :

```powershell
.\native\extio_bridge\scripts\uninstall.ps1
```

Cette disposition — une DLL ExtIO 32 bits dans le dossier de HDSDR — suit la [procédure publiée par HDSDR](https://hdsdr.de/RTLSDR_with_HDSDR.pdf).

## Utiliser

1. Démarrer SDRbridge et le flux RX.
2. Démarrer HDSDR et sélectionner `ExtIO_SDR_Bridge.dll` si HDSDR le demande.
3. Cliquer sur **Start** dans HDSDR.

La fréquence LO et le taux affichés proviennent alors de SDRbridge. Le bouton **SDR-Device [F8]** rappelle que les réglages RF se font dans SDRbridge.

## Construire et vérifier

La cible nécessite Visual Studio Build Tools avec le compilateur C++ Win32 et CMake :

```powershell
.\native\build_native.ps1
.\.venv\Scripts\python.exe -m unittest tests.test_local_clients.LocalClientCompatibilityTests.test_extio_win32_smoke_reads_owned_v2_copies -v
```

Le build produit `native/build/extio_bridge/Release/ExtIO_SDR_Bridge.dll` et `extio_smoke.exe`.
