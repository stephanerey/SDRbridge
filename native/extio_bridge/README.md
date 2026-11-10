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

## Transport, ports et débit

L’ExtIO n’utilise aucune destination UDP. Il ne faut pas créer de port `7355`
ou `7356` pour HDSDR et aucun port IQ ne se configure dans son interface :

- `127.0.0.1:47631/TCP` sert à enregistrer le client local et à recevoir le
  descripteur du ring ;
- le flux IQ `CS16` est lu dans le ring SDBR v2 en mémoire partagée ;
- le port client TCP éphémère est choisi automatiquement par Windows.

La DLL s’enregistre sans profil de sortie et lit donc le ring maître au débit
complet de la source. Elle ne propose pas la décimation par client disponible
pour les destinations UDP. À 2 MS/s en `CS16`, chaque instance représente
64 Mb/s de débit IQ logique ; à 10 MS/s, 320 Mb/s.

Toutes les instances HDSDR ouvrent le même ring, écrit une seule fois par
SDRbridge. Elles apparaissent chacune comme un consommateur local et sont
incluses dans **Débit IQ logique**, mais pas dans **Débit UDP utile** ou le
débit réseau mesuré. Chaque instance recopie toutefois les blocs dans son
propre processus et exécute son propre traitement DSP.

## Hôtes compatibles

`ExtIO_SDR_Bridge.dll` est une DLL Win32 conforme à l’interface ExtIO utilisée
par HDSDR et par l’hôte ExtIO séparé de SDRuno. La matrice de la version 0.6
est volontairement stricte :

- **certifiés :** HDSDR 2.81a et SDRuno 1.42.1710 via
  `SDRuno.EXTIO.exe` ;
- **non garanti :** tout autre logiciel, même s’il annonce ExtIO, tant que sa
  version, son architecture et son cycle Start/Stop n’ont pas été testés.

Une application 64 bits ne peut pas charger directement cette DLL 32 bits.

Pour SDRuno, copier la DLL dans
`C:\Program Files (x86)\SDRplay\SDRuno`, démarrer SDRbridge, puis lancer
`SDRuno.EXTIO.exe`. Ne pas lancer `SDRuno.exe`, qui cherche à utiliser le RSP
directement. La qualification réelle vérifie `In SR: 2000000`, PLAY/STOP, le
spectre SP1 et la connexion locale à `47631`. SDRuno reçoit, comme HDSDR, le
débit complet du ring maître et n’utilise aucun port UDP.

## Construire et vérifier

La cible nécessite Visual Studio Build Tools avec le compilateur C++ Win32 et CMake :

```powershell
.\native\build_native.ps1
.\.venv\Scripts\python.exe -m unittest tests.test_local_clients.LocalClientCompatibilityTests.test_extio_win32_smoke_reads_owned_v2_copies -v
```

Le build produit `native/build/extio_bridge/Release/ExtIO_SDR_Bridge.dll` et `extio_smoke.exe`.
