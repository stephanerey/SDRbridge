# Rapport de qualification SDRbridge 0.4.0

## Résultat du 15 octobre 2026

| Domaine | État | Preuve |
|---|---|---|
| Tests applicatifs | Vert | 48/48 `unittest` |
| Inventaire Soapy | Vert | RSPdx `2001077942`, RSP1 `0000000001`, backend MSi2500 détectés |
| RX Soapy séparé | Vert | RSPdx ≈ 1,915 MS/s ; RSP1 ≈ 1,919 MS/s ; zéro drop/erreur |
| Deux processus, natif + Soapy | Vert | RSPdx ≈ 1,910 MS/s et RSP1 ≈ 1,934 MS/s simultanément ; zéro drop/erreur |
| Deux processus SoapySDRPlay | Rouge | le second flux tombe à ≈ 52 kS/s avec le module Pothos 2021/API 3.07 |
| Paquet portable 0.4.0 | Vert | `--version` et inventaire Soapy terminent avec le code 0 |
| Installateur 0.4.0 | Vert | installation isolée, exécution, connecteurs présents et désinstallation complète |
| Fonctionnel simulé 10 min | Rouge historique | drops tardifs du dispatcher ; endurance 60 min non lancée |

La configuration matérielle simultanée retenue est donc un processus avec le RSPdx via le backend natif SDRplay et un second processus avec le clone RSP1 via Soapy. Les deux sources ont reçu pendant 10 secondes à leur débit attendu, sans drop de file ni erreur de source. Le test RX n'active aucun chemin TX.

Les rapports reproductibles sont enregistrés dans :

- `output/hardware-smoke-v0.4/sequential.json` ;
- `output/hardware-smoke-v0.4-allsoapy/simultaneous.json` ;
- `output/hardware-smoke-v0.4-mixed/simultaneous.json` ;
- `output/device-list-packaged-final/sdrbridge.log`.

Le module `sdrPlaySupport.dll` installé avec PothosSDR date de 2021 et annonce une construction pour l'API SDRplay 3.07 alors que l'API installée est 3.15. L'échec de deux processus Soapy simultanés reste donc une limite de la pile locale ; il ne remet pas en cause le mode mixte vérifié.

## Binaire livré localement

- installateur : `release-v0.4/installer/SDRbridge_Setup_0.4.0.exe` ;
- SHA-256 installateur : `7FD9131EB4C0EC467C22B7EE288BFA514CBE9EDC6C300DA61C5DF93C4DDC2FFB` ;
- exécutable portable : `release-v0.4/SDR_Bridge/SDR_Bridge.exe` ;
- SHA-256 exécutable : `27627269C60A22EEFB52AE48C5A3D50203F00F410543554CC573A211DB3D5D31`.

L'installateur n'est pas signé par un certificat d'éditeur. Windows peut afficher un avertissement SmartScreen. Le dossier généré `release-v0.4` n'est pas versionné dans Git ; l'installateur validé est publié séparément comme fichier joint à la release GitHub v0.4.0.

Le smoke installé ouvre réellement la fenêtre `SDRbridge 0.4.0 — RX — default` avec la configuration Soapy, puis la ferme proprement avec le code 0. Le Qt 5.15.2 embarqué est initialisé avant le runtime Pothos Qt 5.15.3 afin d'éviter le mélange de DLL observé dans la première construction.

## Commandes reproductibles

```powershell
cd E:\PLDesign\SDRbridge
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m sdr_bridge.app --source soapy --list-devices
.\.venv\Scripts\python.exe scripts\run_hardware_smoke.py `
  --device-id 'soapy:sdrplay:2001077942' `
  --device-id 'soapy:sdrplay:0000000001' --duration 8
.\.venv\Scripts\python.exe scripts\run_hardware_smoke.py `
  --device-id 'native-sdrplay:first-available' `
  --device-id 'soapy:sdrplay:0000000001' --duration 10 --simultaneous
.\packaging\build_exe.ps1
```

Le script matériel vérifie qu'au moins 80 % du taux demandé est effectivement reçu. Un processus lent ne peut donc plus produire un faux résultat vert.

## Gate d'endurance encore ouvert

La v0.4 ne revendique pas encore une qualification d'endurance complète. Le run simulé final de 10 minutes avec file 256 avait produit 783 drops entre 570,8 et 597,5 secondes. Une passe de 30 secondes sous forte charge machine avait aussi échoué avec et sans Qt. L'endurance 60 minutes reste interdite tant qu'un smoke au repos puis un nouveau run de 10 minutes ne sont pas verts.

## Périmètre restant

- aucune clé RTL2832 réelle n'a encore été testée ;
- l'USRP B100 n'a pas encore été branché ni qualifié via UHD/Soapy ;
- LAN/VPN, pare-feu et QMAP/Linrad restent hors verdict ;
- le module SoapySDRPlay doit être réévalué avec une construction compatible API 3.15 avant de retester deux backends Soapy simultanés.
