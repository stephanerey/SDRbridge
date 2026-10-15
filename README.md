# SDRbridge

SDRbridge est un répartiteur RX pour Windows : il ouvre une seule source SDR, publie son flux IQ et permet à plusieurs applications de réception de l’utiliser simultanément sans leur donner le contrôle du matériel.

La version 0.4 prend en charge une source simulée, le replay SigMF, le backend natif SDRplay et un backend générique SoapySDR. Soapy énumère les récepteurs connectés par modèle et numéro de série ; les périphériques audio exposés par PothosSDR sont exclus de la liste.

![Deux instances de SDR++, HDSDR et SDRbridge partageant le même flux RX](docs/assets/sdrbridge-three-clients.png)

*Trois clients connectés au même bridge : deux instances SDR++ via SDBU v2 et HDSDR via ExtIO. SDRbridge reste l’unique autorité sur la fréquence centrale et les réglages du récepteur.*

## Ce que fait le projet

- acquisition RX depuis une source unique : SDRplay natif, SoapySDR, simulation ou replay SigMF ;
- distribution locale multiprocessus par ring partagé SDBR v2 ;
- transport UDP SDBU v2 avec métadonnées de fréquence, taux, format, séquence et époque ;
- profils DSP partagés `CS16`/`CF32`, notamment 2 MS/s, 192 kS/s et 96 kS/s ;
- interface Qt pour la radio, les sorties, les profils RF, les captures et les diagnostics ;
- connecteur natif SDR++ x64, ExtIO HDSDR Win32 et shim ANTRACK ;
- capture et replay SigMF 1.2.6 ;
- fonctionnement strictement RX : aucun chemin TX n’est activé.

```text
SDR / simulation / replay
          |
      SDRbridge
       /  |  \
 SDBU v2 SDBR v2  capture SigMF
    |       |
  SDR++   HDSDR / ANTRACK
```

Les applications clientes sont en lecture seule. Changer une fréquence dans SDR++ ou HDSDR ne reconfigure pas le RSPdx : la valeur effective du bridge est réappliquée au client.

## Compatibilité avec les récepteurs SDR

| Récepteur | Chemin prévu | État vérifié |
|---|---|---|
| SDRplay RSPdx | backend natif SDRplay ou SoapySDR | RX réel vérifié à 2 MS/s |
| Clone RSP1 / MSI Panadapter | SoapySDRPlay | RX réel vérifié seul et simultanément avec le RSPdx natif |
| RTL2832 / RTL-SDR | backend SoapySDR avec `SoapyRTLSDR` | implémenté dans le code, non testé avec une clé réelle |
| Airspy, HackRF, LimeSDR, UHD, etc. | module SoapySDR correspondant | compatibilité potentielle, non qualifiée |

Une clé RTL2832 n’est donc **pas encore qualifiée avec SDRbridge**. Elle nécessite au minimum le pilote WinUSB adapté et un runtime SoapySDR x64 avec le module `SoapyRTLSDR`. La couche d’exécution Soapy est intégrée au paquet v0.4 ; le périphérique doit ensuite apparaître dans la liste de la page **Radio**.

Sur la machine de développement, PothosSDR expose bien la factory `rtlsdr`, mais aucune clé RTL2832 n’était connectée pendant cette vérification. Cette présence logicielle ne constitue pas une preuve de réception matérielle.

## Installer SDRbridge

### Installation simple pour un utilisateur final

La version publiée actuelle est la **v0.4.0**. Le fichier recommandé est **`SDRbridge_Setup_0.4.0.exe`**, disponible dans la [release GitHub v0.4.0](https://github.com/stephanerey/SDRbridge/releases/tag/v0.4.0). Il contient l’application et ses dépendances Python : l’utilisateur le lance, suit l’assistant, puis démarre SDRbridge depuis le menu Démarrer ou le raccourci du Bureau. Il n’a besoin ni de Python, ni de Git, ni de Visual Studio. Les pilotes matériels, et PothosSDR pour le backend Soapy, restent des prérequis externes.

**`SDR_Bridge.exe` ne doit pas être copié seul.** Le build actuel est une application portable « en dossier » : l’exécutable dépend des DLL et du répertoire `_internal` placés à côté de lui. Deux distributions sont donc possibles :

- recommandée : le fichier unique `SDRbridge_Setup_0.4.0.exe` ;
- portable : une archive ZIP contenant le dossier `SDR_Bridge` complet, à extraire sans déplacer l’exécutable hors de ce dossier.

Pour utiliser un RSPdx, le pilote et l’API SDRplay officiels doivent aussi être installés sur le PC. Ils ne sont pas remplacés par SDRbridge. Les connecteurs SDR++ et HDSDR s’installent ensuite avec les procédures dédiées plus bas.

> Le dépôt Git versionne les sources et les DLL clientes, pas le paquet principal généré `release-v0.4`. L’installateur validé est publié séparément comme fichier joint à la release GitHub.

### Construire la distribution depuis les sources

#### 1. Installer les prérequis

- Windows 10 ou 11 x64 ;
- Git ;
- Python 3.12 x64 ;
- Visual Studio Build Tools avec **Développement Desktop en C++** et CMake ;
- l’[API SDRplay](https://www.sdrplay.com/api/) si le RSPdx ou le backend natif SDRplay doit être utilisé ;
- Inno Setup 6, facultatif, uniquement pour produire un assistant `Setup.exe`.

#### 2. Cloner et préparer l’environnement

```powershell
git clone https://github.com/stephanerey/SDRbridge.git
cd SDRbridge
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -r packaging\requirements-build.txt
```

#### 3. Construire le paquet Windows

```powershell
.\packaging\build_exe.ps1
```

Le script lit la version dans `pyproject.toml`, compile les composants natifs x64/Win32 et place le résultat dans `release-v0.4` :

- `release-v0.4\SDR_Bridge\SDR_Bridge.exe` : application portable ;
- `release-v0.4\SDR_Bridge_Client` et `SDR_Bridge_Native_Client` : clients de diagnostic ;
- `release-v0.4\Connectors` : connecteurs SDR++, HDSDR et ANTRACK, avec leurs scripts d’installation ;
- `release-v0.4\installer\SDRbridge_Setup_0.4.0.exe` : installateur créé si Inno Setup 6 est présent.

Pour une installation classique, lancer `SDRbridge_Setup_0.4.0.exe`. L’application est installée dans le profil utilisateur (`%LOCALAPPDATA%\Programs\SDRbridge`) et ne demande pas de droits administrateur. Sans Inno Setup, copier ou compresser **tout** le dossier `release-v0.4\SDR_Bridge` pour constituer la version portable.

#### 4. Premier démarrage

Tester d’abord l’application sans matériel :

```powershell
.\release-v0.4\SDR_Bridge\SDR_Bridge.exe --source simulated
```

Pour le RSPdx avec la configuration fournie :

```powershell
.\release-v0.4\SDR_Bridge\SDR_Bridge.exe --config .\config.soapy-sdrpp.json
```

Le raccourci créé par l’installateur charge `config.soapy-sdrpp.json` : la liste **Source** contient donc les SDR détectés par Soapy. La réception reste arrêtée jusqu’au clic sur **Start**. Un lancement direct de `SDR_Bridge.exe` sans argument conserve la source simulée comme mode sûr.

### Journaux et diagnostic d’arrêt

SDRbridge écrit automatiquement des journaux JSON rotatifs dans :

```text
%LOCALAPPDATA%\SDRbridge\logs\sdrbridge.log
```

Les cinq archives précédentes sont conservées, avec une taille maximale de 5 Mio par fichier. Chaque exécution possède un `run_id` commun au journal et au contrôle natif. Les démarrages, arrêts, erreurs de source, pertes de file et exceptions Python non interceptées y sont enregistrés sans données IQ ni jeton de session.

Les fautes natives que Python peut intercepter sont écrites séparément dans `sdrbridge-fault.log`. Le chemin du journal courant apparaît aussi dans l’onglet **Diagnostics**. Pour une exécution de développement isolée, `--log-dir PATH` permet de choisir un autre dossier.

### Plusieurs instances et plusieurs SDR

La v0.4 conserve une source active par processus. Plusieurs processus peuvent fonctionner simultanément grâce à un nom d’instance, des ports décalés, des rings distincts et des journaux séparés. Sur la machine de référence, la combinaison vérifiée est : RSPdx par le backend natif et RSP1 par Soapy.

```powershell
.\start-sdrbridge.ps1 -Instance rspdx -Config .\config.native-sdrpp.json
.\start-sdrbridge.ps1 -Instance rsp1 -PortOffset 100 `
  -Config .\config.soapy-sdrpp.json `
  -DeviceId 'soapy:sdrplay:0000000001'
```

La première instance utilise les ports `47631`/`47632` et UDP `7355`. La seconde utilise `47731`/`47732` et UDP `7455`. Ses journaux se trouvent sous `%LOCALAPPDATA%\SDRbridge\instances\rsp1\logs`.

Avec le module SoapySDRPlay fourni par PothosSDR 2021, deux processus utilisant tous les deux Soapy ne sont pas qualifiés : le second RSP peut recevoir très en dessous de 2 MS/s. Le mode mixte natif + Soapy a tenu les deux flux simultanément sans perte pendant le smoke matériel. Cette réserve devra être réévaluée avec un module SoapySDRPlay construit pour l’API SDRplay 3.15.

## Installer la source SDR++

La source personnalisée a été construite pour **SDR++ 1.3.0 x64**. La DLL précompilée est [`clients/sdrpp_sdbu_source/bin/sdbu_source.dll`](clients/sdrpp_sdbu_source/bin/sdbu_source.dll).

1. Fermer SDR++.
2. Depuis PowerShell à la racine du dépôt, lancer le script avec le chemin de l’installation SDR++ :

```powershell
.\clients\sdrpp_sdbu_source\scripts\install.ps1 `
  -SdrppRoot 'E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64'
```

3. Redémarrer SDR++ et sélectionner **SDRbridge SDBU v2** dans **Source**.
4. Conserver `127.0.0.1` et choisir un port UDP, par défaut `7355`.
5. Dans SDRbridge, ajouter une destination UDP vers ce même port avec le transport `sdbu_v2`.

Chaque instance SDR++ locale doit utiliser son propre port UDP. Le script sauvegarde `config.json`, installe la DLL dans `modules` et crée un manifeste. Le retour arrière est disponible avec :

```powershell
.\clients\sdrpp_sdbu_source\scripts\uninstall.ps1 `
  -SdrppRoot 'E:\Radio\sdrpp_windows_x64_1.3.0\sdrpp_windows_x64'
```

Les détails de compilation et les limites sont dans le [README du connecteur SDR++](clients/sdrpp_sdbu_source/README.md).

## Installer l’ExtIO HDSDR

HDSDR est une application 32 bits ; il faut donc utiliser la DLL Win32 précompilée [`native/extio_bridge/bin/ExtIO_SDR_Bridge.dll`](native/extio_bridge/bin/ExtIO_SDR_Bridge.dll).

1. Fermer HDSDR.
2. Ouvrir PowerShell en tant qu’administrateur depuis la racine du dépôt.
3. Installer la DLL dans le dossier HDSDR :

```powershell
.\native\extio_bridge\scripts\install.ps1
```

Le chemin par défaut est `C:\Program Files (x86)\HDSDR`. Pour une version portable :

```powershell
.\native\extio_bridge\scripts\install.ps1 -HdsdrRoot 'D:\Radio\HDSDR'
```

4. Démarrer SDRbridge avant HDSDR.
5. Dans HDSDR, sélectionner `ExtIO_SDR_Bridge.dll`, puis cliquer sur **Start**.

L’ExtIO se connecte au contrôle local `127.0.0.1:47631`, ouvre le ring SDBR v2 et notifie HDSDR lorsque la fréquence centrale ou le taux d’échantillonnage change. Elle refuse les demandes de syntonisation provenant de HDSDR afin de conserver SDRbridge comme autorité RF.

Pour restaurer la DLL précédente :

```powershell
.\native\extio_bridge\scripts\uninstall.ps1
```

Voir le [README ExtIO](native/extio_bridge/README.md) pour la compilation et le test natif.

## Développement et lancement direct depuis les sources

Pour travailler sans reconstruire le paquet PyInstaller à chaque modification :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\native\build_native.ps1
.\run_bridge.ps1 -Source simulated
```

Le lancement matériel est explicite :

```powershell
.\run_bridge.ps1 -Source native
```

Le paquet portable local, lorsqu’il a été construit, se lance avec `start-sdrbridge.ps1`. Le script utilise `config.soapy-sdrpp.json` par défaut et accepte `-Instance`, `-PortOffset`, `-Config` et `-DeviceId`.

## Vérifier

```powershell
.\run_tests.ps1
```

État vérifié au 15 octobre 2026 : 48 tests applicatifs passent. Le RSPdx et le clone RSP1 sont énumérés par Soapy avec leur série ; chacun reçoit seul à environ 1,92 MS/s, et deux instances mixtes native + Soapy reçoivent simultanément sans perte sur le smoke de 10 secondes. La recette d’endurance intégrée reste ouverte : le projet ne revendique donc pas encore une qualification de performance complète.

## Documentation

- [Point d’entrée du développement](docs/START_HERE.md)
- [État réel et réserves](docs/work/CURRENT_STATE.md)
- [Contrat d’exécution v0.3](docs/specs/06_IMPLEMENTATION_BASELINE.md)
- [PRD](docs/product/PRD.md)
- [Rapport de qualification](docs/verification/QUALIFICATION_REPORT.md)
- [Connecteur SDR++ SDBU v2](clients/sdrpp_sdbu_source/README.md)
- [ExtIO SDRbridge pour HDSDR](native/extio_bridge/README.md)

Dépôt : [stephanerey/SDRbridge](https://github.com/stephanerey/SDRbridge).
